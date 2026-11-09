"""FastConnect V3: decoder, quality policy, collector/replay/ranking, adapter, REST client, ops.

All offline. Frames follow the wire shape read from ssi-sdk 3.3.2; values are synthetic.
"""
from collections import Counter
from datetime import datetime, timedelta, date
import json
import sqlite3

import pytest

from src.analytics.sessions import evaluate_daily, evaluate_run, report_frame, spearman
from src.config import ConfigurationError
from src.data.daily_store import DailyStore, read_daily
from src.data.ssi_journal import BufferedSink, SSIJournal
from src.data.ssi_quality import QualityPolicy, assess_member, policy_for_profile, scheduled_session
from src.data.store import EventStore, TZ, now
from src.neo_api.rest import AuthError, NeoError
from src.ranking.engine import rank_groups
from src.ssi_api.connections import connection_plan, v3_api_base, v3_stream_url
from src.ssi_api.decoder import DecodeError
from src.ssi_api.fake_stream import FakeClock, FakeFactory
from src.ssi_api.replay import replay
from src.ssi_api.settings import SSISettings, load_ssi_settings
from src.ssi_api.stream_collector import Frame, StreamAuthFailed, StreamDisconnected, collect_stream
from src.ssi_api.v3_client import MemberListError, V3Client, canonical_summary, resolve_members
from src.ssi_api.v3_decoder import decode_v3, fan_out, retained_raw, source_time
from src.ssi_api.v3_ops import history, reconcile, smoke, stream_stats, stream_window, stream_window_for
from src.ssi_api.v3_sample import baseline_frames, v3_members, v3_scenario
from src.ssi_api.v3_stream import V3Factory, V3Stream

RECEIVED = "2026-11-04T10:00:05+07:00"


def decode(topic, data, received=RECEIVED):
    return decode_v3({"channel": "DATA", "topic": topic, "data": data}, received_at=received)


# -- decoder -----------------------------------------------------------------------

def test_trade_maps_fields_and_derives_total_value_with_flag():
    item = decode("trade.FPT", {"s": "FPT", "t": "10:00:04", "p": 102000, "q": 100, "v": 5000, "o": 100000, "a": 101000})
    p = item["payload"]
    assert item["profile"] == "fastconnect_v3" and item["message_type"] == "TRADE"
    assert p["closePrice"] == 102000 and p["openPrice"] == 100000 and p["totalTradingVolume"] == 5000
    assert p["totalTradingValue"] == 101000 * 5000
    assert item["metadata"]["derived_fields"] == {"totalTradingValue": "averagePrice*totalTradingVolume"}
    assert {"TOTAL_VALUE_DERIVED", "SOURCE_DATE_FROM_RECEIVED"} <= {i["code"] for i in item["issues"]}
    assert "highPrice" not in p and "lowPrice" not in p  # absent stays absent, never 0
    assert item["source_at"] == "2026-11-04T10:00:04+07:00"


def test_trade_without_average_does_not_invent_value_and_null_invalidates():
    item = decode("trade.FPT", {"s": "FPT", "t": "10:00:04", "p": None, "v": 5000})
    assert item["payload"]["closePrice"] is None and "totalTradingValue" not in item["payload"]
    auction = decode("trade.FPT", {"s": "FPT", "t": "10:00:04", "p": "ATO"})
    assert auction["payload"]["closePrice"] is None
    assert {"code": "AUCTION_PRICE_LABEL", "field": "closePrice"} in auction["issues"]


def test_quote_keeps_three_levels_and_marks_missing_levels():
    bids = [[100 - i, 10 * i] for i in range(1, 11)]
    item = decode("quote.SHS", {"s": "SHS", "t": "10:00:04", "bids": bids, "asks": [{"p": 101, "q": 5}]})
    p = item["payload"]
    assert [p["bidPrice1"], p["bidPrice3"], p["bidVol3"]] == [99, 97, 30]
    assert p["askPrice1"] == 101 and p["askVol1"] == 5 and p["askPrice2"] is None and p["askVol3"] is None
    assert item["metadata"]["bids_levels_received"] == 10
    assert Counter(i["code"] for i in item["issues"])["BOOK_LEVEL_MISSING"] == 2
    labelled = decode("quote.SHS", {"s": "SHS", "t": "10:00:04", "bids": [["ATO", 500]]})
    assert labelled["payload"]["bidPrice1"] == "ATO"


def test_room_maps_foreign_fields_and_keeps_estimation_unknown():
    item = decode("room.VNM", {"s": "VNM", "t": "10:00:04", "bq": 10, "bv": 1e6, "sq": 4, "sv": 4e5, "tr": 100, "cr": 60})
    p = item["payload"]
    assert (p["foreignBuyVolume"], p["foreignBuyValue"], p["foreignSellValue"], p["foreignRemain"]) == (10, 1e6, 4e5, 60)
    assert item["metadata"]["foreign_value_estimated"] is None
    assert item["metadata"]["foreign_value_basis"] == "pending_live_validation"


def test_market_flag_is_board_scoped_and_fans_out_to_that_board_only():
    item = decode("market.flag", {"b": "HOSE", "t": "10:00:04", "f": "LO"})
    assert item["scope"] == {"board": "HOSE"} and item["payload"]["tradingSession"] == "LO"
    members = {m["symbol"]: m for m in v3_members(2)}
    copies = fan_out(item, members)
    assert [c["payload"]["symbol"] for c in copies] == ["V3HOSE01", "V3HOSE02"]
    assert all(c["scope"] is None and c["metadata"]["fanout_board"] == "HOSE" for c in copies)
    unknown = decode("market.flag", {"b": "HNX", "t": "10:00:04", "f": "XYZ"})
    assert unknown["payload"]["tradingSession"] is None
    with pytest.raises(DecodeError):
        decode("market.flag", {"b": "MARS", "f": "LO"})


@pytest.mark.parametrize("value,expected,issue", [
    (int(datetime(2026, 11, 4, 10, 0, 3, tzinfo=TZ).timestamp() * 1000), "2026-11-04T10:00:03+07:00", None),
    ("2026-11-04T03:00:03Z", "2026-11-04T10:00:03+07:00", None),
    ("2026-11-04 10:00:03", "2026-11-04T10:00:03+07:00", None),
    ("100003", "2026-11-04T10:00:03+07:00", "SOURCE_DATE_FROM_RECEIVED"),
    ("bad", None, "INVALID_OR_INCOMPLETE_SOURCE_TIME"),
    (None, None, "SOURCE_TIME_UNAVAILABLE"),
])
def test_source_time_formats_are_explicit(value, expected, issue):
    at, code = source_time(value, datetime(2026, 11, 4, 10, 0, 5, tzinfo=TZ))
    assert (at.isoformat() if at else None) == expected and code == issue


@pytest.mark.parametrize("raw", [
    {"channel": "DATA", "topic": "trade.index.VN30", "data": {"s": "VN30"}},
    {"channel": "DATA", "topic": "trade.FPT@1m", "data": {"s": "FPT"}},
    {"channel": "DATA", "data": {"s": "FPT"}},
    {"channel": "DATA", "topic": "trade.FPT"},
    {"channel": "DATA", "topic": "trade.FPT", "data": {"s": "F P T"}},
    "not json",
])
def test_unsupported_or_malformed_frames_raise_safe_errors(raw):
    with pytest.raises(DecodeError):
        decode_v3(raw, received_at=RECEIVED)


def test_retained_raw_keeps_only_decoder_fields():
    raw = {"channel": "DATA", "topic": "trade.FPT",
           "data": {"s": "FPT", "t": "10:00:04", "p": 1, "secret": "SENTINEL", "note": "x" * 100}}
    kept = retained_raw(raw, decode_v3(raw, received_at=RECEIVED))
    assert kept["data"] == {"s": "FPT", "t": "10:00:04", "p": 1}
    assert "SENTINEL" not in json.dumps(kept)


# -- quality policy ----------------------------------------------------------------------

def test_policy_validation_and_profile_relaxation():
    with pytest.raises(ValueError):QualityPolicy(max_age_seconds=True)
    with pytest.raises(ValueError):QualityPolicy(session_fallback="guess")
    base = QualityPolicy()
    assert policy_for_profile(base, "fcdata_v2") is base
    v3 = policy_for_profile(base, "fastconnect_v3")
    assert v3.require_symbol_status is False and v3.session_fallback == "schedule"
    assert "tradingStatus" not in v3.needed() and "tradingStatus" in base.needed()
    assert (v3.max_age_seconds, v3.limits("closePrice"), v3.limits("foreignBuyValue")) == (120, (120, 10), (100, 35))
    assert base.limits("foreignBuyValue") == (60, 10)  # FCData v2 keeps the general limits
    chosen = policy_for_profile(QualityPolicy(max_age_seconds=45), "fastconnect_v3")
    assert chosen.limits("foreignBuyValue") == (45, 10) and chosen.session_fallback == "schedule"
    with pytest.raises(ValueError):QualityPolicy(foreign_max_age_seconds=-1)


def fresh_state(foreign_age=0, foreign_lag=0, price_age=0):
    """All needed fields one second old, except the ages and lags asked for. Clock: 10:00:00."""
    at = datetime.fromisoformat("2026-11-04T10:00:00+07:00")
    stamp = lambda seconds: (at - timedelta(seconds=seconds)).isoformat()
    payload, updated, received = {}, {}, {}
    for key in QualityPolicy().needed():
        payload[key] = 100.0
        age, lag = (foreign_age + foreign_lag, foreign_lag) if key in {"foreignBuyValue", "foreignSellValue"} else (
            (price_age, 0) if key in {"closePrice", "totalTradingValue"} else (1, 0))
        updated[key], received[key] = stamp(age), stamp(age - lag)
    payload.update(tradingSession="LO", tradingStatus="NORMAL")
    return {"payload": payload, "field_updated_at": updated, "field_received_at": received}, at.isoformat()


@pytest.mark.parametrize("state_args,reason", [
    ({"foreign_age": 60, "foreign_lag": 30}, None),      # a normal late batch, 90 s old: usable
    ({"foreign_age": 125}, "STALE_FIELDS"),              # one batch missed
    ({"foreign_age": 5, "foreign_lag": 40}, "EXCESS_RECORDED_LAG"),
    ({"price_age": 110}, None),                          # a quiet stock with a live connection
    ({"price_age": 130}, "STALE_FIELDS")])
def test_measured_limits_are_applied_per_field(state_args, reason):
    state, at = fresh_state(**state_args)
    policy = policy_for_profile(QualityPolicy(), "fastconnect_v3")
    row = assess_member({"symbol": "FPT", "marketCode": "HOSE", "index_group": "VN30"}, state, at, "connected", policy)
    assert row["reasons"] == ([reason] if reason else []) and row["data_usable"] is (reason is None)


@pytest.mark.parametrize("market,clock,session", [
    ("HOSE", "09:05", "ATO"), ("HOSE", "09:20", "LO"), ("HOSE", "11:45", "BREAK"), ("HOSE", "14:35", "ATC"),
    ("HNX", "09:05", "LO"), ("HNX", "14:50", "C"), ("HOSE", "14:50", "C"), ("HNX", "15:10", "C"), ("UPCOM", "10:00", None)])
def test_published_timetable(market, clock, session):
    at = datetime.fromisoformat(f"2026-11-04T{clock}:00+07:00")
    assert scheduled_session(market, at) == session
    assert scheduled_session("HOSE", datetime.fromisoformat("2026-11-07T10:00:00+07:00")) == "C"  # Saturday


# -- collector → journal → replay → ranking ------------------------------------------

class V3FakeFactory(FakeFactory):
    profile = "fastconnect_v3"


def collect_v3(path, scripts=None, members=None, **kwargs):
    if scripts is None:
        members, scripts = v3_scenario(**kwargs)
    clock = FakeClock()
    store = EventStore(path)
    sink = BufferedSink(store)
    factory = V3FakeFactory(members, scripts, clock)
    try:
        result = collect_stream(factory, sink, seconds=90, max_messages=1000, idle_seconds=120,
                                clock=clock.monotonic, sleep=clock.sleep, wall_now=clock.wall_now)
        sink.flush()
    finally:
        store.close()
    return result, factory


def test_v3_pipeline_ranks_vn30_and_rebuilds_after_disconnect(tmp_path):
    path = tmp_path / "v3.sqlite"
    result, factory = collect_v3(path)
    assert result["profile"] == "fastconnect_v3" and result["counters"]["decode_errors"] == 0
    assert result["counters"]["reconnects"] == 1 and factory.bootstrap_calls == 2
    assert "trade.VN30@*" in factory.sessions[0].channels and "market.flag" in factory.sessions[0].channels
    first = replay(path, result["run"], as_of="2026-11-04T10:00:20+07:00")
    assert first["profile"] == "fastconnect_v3" and first["policy"]["require_symbol_status"] is False
    assert all(row["data_usable"] for row in first["rows"])
    assert {"SYMBOL_STATUS_NOT_PROVIDED", "TOTAL_VALUE_DERIVED"} <= {w for row in first["rows"] for w in row["warnings"]}
    ranked = rank_groups(report_frame(first), semantics_verified=True)
    assert ranked.groupby("index_group")["rank"].count().to_dict() == {"VN30": 11}
    gap = replay(path, result["run"], as_of="2026-11-04T10:00:45+07:00")
    assert all("NO_BASELINE" in row["reasons"] for row in gap["rows"])
    as_real = report_frame(first).assign(source="ssi")
    gated = rank_groups(as_real, semantics_verified=False)
    assert gated["rank"].isna().all()  # real-source ranking stays locked until semantics are verified


def test_missing_session_flag_falls_back_to_timetable_with_warning(tmp_path):
    path = tmp_path / "noflag.sqlite"
    result, _ = collect_v3(path, flag=False)
    report = replay(path, result["run"], as_of="2026-11-04T10:00:20+07:00")
    assert all(row["session_basis"] == "schedule" and row["trading_session"] == "LO" for row in report["rows"])
    assert all("SESSION_FROM_SCHEDULE" in row["warnings"] and row["data_usable"] for row in report["rows"])
    members, _ = v3_scenario(flag=False)
    lunch = [baseline_frames(members, datetime.fromisoformat("2026-11-04T11:45:00+07:00"), flag=False)]
    path2 = tmp_path / "lunch.sqlite"
    result2, _ = collect_v3(path2, lunch, members)
    late = replay(path2, result2["run"], as_of="2026-11-04T11:45:10+07:00")
    assert all("SESSION_NOT_LO" in row["reasons"] for row in late["rows"])


def test_session_evaluation_reports_stability_and_intervals(tmp_path):
    path = tmp_path / "eval.sqlite"
    result, _ = collect_v3(path)
    evaluated = evaluate_run(path, result["run"], every_minutes=0.25)
    ranked_points = [p for p in evaluated["checkpoints"] if p["groups"]["VN30"]["ranked"] == 11]
    assert ranked_points and evaluated["exploratory_ranking"] is True
    assert any(p["groups"]["VN30"]["spearman_vs_previous"] is not None for p in ranked_points)
    quote = evaluated["update_intervals"]["quote"]  # the probe re-quotes once, 29 s after its baseline
    assert quote["gaps"] == 1 and quote["p50"] == 29 and quote["share_within"]["30"] == 1
    assert "trade" not in evaluated["update_intervals"]  # no gap is measured across the reconnect
    assert spearman({"a": 1, "b": 2, "c": 3}, {"a": 3, "b": 2, "c": 1}) == pytest.approx(-1)
    assert spearman({"a": 1, "b": 2}, {"a": 1, "b": 2}) is None


# -- stream adapter ----------------------------------------------------------------------

class FakeWS:
    def __init__(self, client=None, script=(), fail=None):
        self.handlers, self.sent, self.script, self.fail = {}, [], list(script), fail
        self.on_state, self.disconnected = None, False

    def on(self, channel, handler):
        self.handlers[channel] = handler

    def connect(self):
        if self.fail:
            raise self.fail

    def send(self, data):
        self.sent.append(data)
        for item in self.script:
            if callable(item):
                item(self)
            else:
                self.handlers["DATA"](item)

    def disconnect(self):
        self.disconnected = True


def test_adapter_delivers_raw_frames_and_maps_failures():
    ws = FakeWS(script=[{"channel": "DATA", "topic": "trade.FPT", "data": {"s": "FPT"}},
                        {"channel": "DATA", "method": "subscribe", "status": "ok"}])
    stream = V3Stream(object(), ws_factory=lambda client: ws, clock=lambda: RECEIVED)
    stream.connect()
    stream.subscribe(("trade.VN30@*",))
    assert ws.sent == [{"method": "subscribe", "channel": "DATA", "topics": ["trade.VN30@*"]}]
    frame = stream.receive(0)
    assert isinstance(frame, Frame) and frame.raw["topic"] == "trade.FPT" and stream.acks == {"ok": 1, "error": 0}
    assert stream.receive(0) is None
    ws.handlers["DATA"]({"channel": "DATA", "method": "subscribe", "status": "error", "message": "Denied (scope)"})
    with pytest.raises(StreamAuthFailed):
        stream.receive(0)
    ws.on_state(type("E", (), {"state": "disconnected", "error": None})())
    with pytest.raises(StreamDisconnected):
        stream.receive(0)
    stream.close()
    assert ws.disconnected


def test_adapter_connect_errors_and_overflow():
    from ssi_sdk.exceptions import AuthenticationError, WebSocketError
    auth = V3Stream(object(), ws_factory=lambda c: FakeWS(fail=AuthenticationError("x")))
    with pytest.raises(StreamAuthFailed):auth.connect()
    drop = V3Stream(object(), ws_factory=lambda c: FakeWS(fail=WebSocketError("x")))
    with pytest.raises(StreamDisconnected):drop.connect()
    small = V3Stream(object(), ws_factory=lambda c: FakeWS(), clock=lambda: RECEIVED, limit=1)
    small.connect()
    for _ in range(2):
        small.ws.handlers["DATA"]({"channel": "DATA", "topic": "trade.A", "data": {}})
    with pytest.raises(StreamDisconnected):small.receive(0)


def test_factory_topics():
    members = v3_members(1)
    by_index = V3Factory(None).topics(members)
    assert by_index == ("trade.VN30@*", "quote.VN30@*", "room.VN30@*", "market.flag")
    by_symbol = V3Factory(None, subscribe_mode="symbols").topics(members)
    assert "quote.V3HOSE01" in by_symbol and by_symbol[-1] == "market.flag"
    with pytest.raises(ValueError):V3Factory(None, subscribe_mode="all")


# -- REST client -----------------------------------------------------------------------------

class Pages(list):
    """Successive responses for one route (a plain list is a single bare-array response)."""


class FakeRest:
    def __init__(self, responses):
        self.responses, self.calls = responses, []

    def get(self, path, params=None):
        self.calls.append((path, dict(params or {})))
        item = self.responses[path]
        result = item.pop(0) if isinstance(item, Pages) else item
        if isinstance(result, Exception):
            raise result
        return result


class FakeTokens:
    has_refresh_token, token = False, None

    def __init__(self, auth):
        self.auth = auth

    def request_otp_typed(self):
        self.auth.events.append("smart")
        return type("R", (), {"transaction_id": "T1"})()

    def ensure_authenticated(self):
        return "TOKEN"


class FakeAuth:
    def __init__(self, rest=None):
        self.events, self.rest_client = [], rest or FakeRest({})
        self.token_manager = FakeTokens(self)

    def authenticate(self, otp=None, transaction_id=None):
        self.events.append(("auth", otp))

    def request_otp(self):
        self.events.append("request_otp")

    def ensure_authenticated(self, transaction_id=None):
        self.events.append(("ensure", transaction_id))


V3_SETTINGS = SSISettings(profile="fastconnect_v3", api_key="k", api_secret="s")


def client_with(responses=None):
    auth = FakeAuth(FakeRest(responses or {}))
    client = V3Client(V3_SETTINGS, auth_factory=lambda: auth)
    return client, auth


def test_login_modes_never_keep_the_otp():
    client, auth = client_with()
    with pytest.raises(AuthError):client.get("securitiesSummary")
    assert client.login("none") == "none" and auth.events == [("auth", None)]
    client, auth = client_with()
    client.login("prompt", read_otp=lambda: "123456", notify=lambda _: None)
    assert auth.events == ["request_otp", ("auth", "123456")] and "123456" not in json.dumps(vars(client), default=str)
    with pytest.raises(NeoError):client.login("prompt", read_otp=lambda: "12ab", notify=lambda _: None)
    client, auth = client_with()
    client.login("smart", notify=lambda _: None)
    assert auth.events == ["smart", ("ensure", "T1")]
    with pytest.raises(ConfigurationError):V3Client(SSISettings(profile="fcdata_v2", consumer_id="a", consumer_secret="b"))


def test_index_members_validate_board_and_routes_are_allow_listed():
    rows = [{"symbol": "FPT", "board": "HOSE", "index": "VN30"}, {"symbol": "VNM", "board": "HOSE"}]
    rows += [{"symbol": f"AA{i:02d}", "board": "HOSE"} for i in range(28)]
    client, auth = client_with({"/api/v3/data/securitiesByBoard": rows})
    client.login("none")
    assert client.index_members("VN30")[:2] == [{"symbol": "FPT", "index_group": "VN30", "marketCode": "HOSE"},
                                                {"symbol": "VNM", "index_group": "VN30", "marketCode": "HOSE"}]
    assert auth.rest_client.calls[0] == ("/api/v3/data/securitiesByBoard", {"index": "VN30"})
    with pytest.raises(NeoError):client.index_members("HNX30")  # outside the VN30-only scope
    with pytest.raises(NeoError):client.get("trading/order")
    empty, _ = client_with({"/api/v3/data/securitiesByBoard": {"code": 204}})
    empty.login("none")
    with pytest.raises(NeoError):empty.index_members("VN30")


INDEX_ROW = {"symbol": "VN30", "board": "HOSE", "symbolNameVi": None, "listedShare": None}  # live reply, 09/11/2026 15:49


@pytest.mark.parametrize("rows", [[INDEX_ROW], [{"symbol": "FPT", "board": "HOSE"}], {"code": 204}])
def test_reply_that_is_not_the_composition_is_refused(rows):
    client, _ = client_with({"/api/v3/data/securitiesByBoard": rows})
    client.login("none")
    with pytest.raises(MemberListError):client.index_members("VN30")


def stored_days(path, *sizes):
    rows = [{"symbol": f"S{i:02d}", "index_group": "VN30", "tradingDate": f"2026-11-0{d + 1}"}
            for d, size in enumerate(sizes) for i in range(size)]
    with DailyStore(path) as store:
        store.upsert("ssi", rows, "2026-11-09T15:00:00+07:00")


@pytest.mark.parametrize("clock,label", [("08:10", "sang"), ("11:34", "sang"), ("11:36", "chieu"), ("15:04", "chieu"), ("15:05", None)])
def test_stream_window_is_chosen_by_the_clock(clock, label):
    window = stream_window_for(datetime.fromisoformat(f"2026-11-10T{clock}:00+07:00"))
    assert (window[0] if window else None) == label


def run_window(tmp_path, at, **options):
    moments = {"now": datetime.fromisoformat(at)}
    logins = []

    def login():
        logins.append(1)
        client = SmokeClient(v3_members(11))
        client.close = lambda: None
        return client

    def sleep(seconds):
        moments["now"] += timedelta(seconds=seconds)

    return stream_window(V3_SETTINGS, login, clock=lambda: moments["now"], sleep=sleep, database=tmp_path / "s.sqlite",
                         out_root=tmp_path / "out", ws_factory=lambda c: FakeWS(script=[]), **options), moments, logins


def test_stream_window_does_nothing_once_over_or_at_the_weekend_or_already_done(tmp_path):
    for at in ("2026-11-10T15:10:00+07:00", "2026-11-14T09:00:00+07:00"):
        result, _, logins = run_window(tmp_path, at)
        assert "skipped" in result and not logins
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "stream-2026-11-10-sang.json").write_text("{}", encoding="utf-8")
    result, _, logins = run_window(tmp_path, "2026-11-10T09:00:00+07:00")
    assert "đã có" in result["skipped"] and not logins


def test_stream_window_waits_for_the_start_and_keeps_no_prices(tmp_path, monkeypatch):
    def fake_collect(settings, client, *, seconds, database, ws_factory):
        fake_collect.seconds = seconds
        return {"run": "r1", "stop_reason": "duration_limit", "counters": {"received": 0}, "acks": {"ok": 1, "error": 0}}

    monkeypatch.setattr("src.ssi_api.v3_ops.collect", fake_collect)
    monkeypatch.setattr("src.ssi_api.v3_ops.stream_stats", lambda path, run: {"lag_seconds": {}, "session_flags": []})
    monkeypatch.setattr("src.ssi_api.v3_ops.evaluate_run", lambda *a, **k: 1 / 0)
    result, moments, logins = run_window(tmp_path, "2026-11-10T08:30:00+07:00")
    assert logins and moments["now"] >= datetime.fromisoformat("2026-11-10T08:55:00+07:00")
    assert fake_collect.seconds == 160 * 60 and result["window"] == "sang" and "ZeroDivisionError" in result["analysis_error"]
    saved = json.loads((tmp_path / "out" / "stream-2026-11-10-sang.json").read_text(encoding="utf-8"))
    assert saved["counters"] == {"received": 0} and saved["acks"]["ok"] == 1 and "analysis_error" in saved


def test_stream_stats_reads_flags_of_the_board_and_connection_changes(tmp_path):
    db = tmp_path / "s.sqlite"
    store = EventStore(db)
    write = lambda channel, payload, at: store.append(source="ssi", run="r1", received_at=f"2026-11-10T{at}+07:00", channel=channel, payload=payload)
    write("connection", {"state": "connected", "connection_epoch": 1}, "13:00:00")
    write("connection", {"state": "duplicate", "connection_epoch": 1}, "13:00:01")
    room = lambda at: {"connection_epoch": 1, "message": {"message_type": "ROOM", "data": {"s": "FPT", "t": f"2026/11/10 {at}"}}}
    write("ssiRaw", room("13:00:00"), "13:00:20")
    write("ssiRaw", room("13:01:00"), "13:01:20")
    for board, flag in (("HNX", "ATC"), ("HOSE", "ATC")):
        write("ssiRaw", {"connection_epoch": 1, "message": {"message_type": "MARKET_FLAG", "data": {"b": board, "f": flag, "t": "2026/11/10 14:30:00"}}}, "14:30:00")
    store.close()
    stats = stream_stats(db, "r1")
    assert stats["lag_seconds"]["ROOM"]["p50"] == 20 and stats["gap_seconds"]["ROOM"]["p50"] == 60
    assert [f["flag"] for f in stats["session_flags"]] == ["ATC"] and [c["state"] for c in stats["connections"]] == ["connected"]


def test_summaries_paginate_and_keep_absent_fields_none():
    page1 = {"data": [{"symbol": "FPT", "tradingDate": "2026-11-04", "open": "100", "close": 102, "totalMatchValue": 5e9}],
             "pagesCount": 2}
    page2 = {"data": [{"symbol": "VNM", "tradingDate": "04/11/2026", "open": 50, "close": "x"}], "pagesCount": 2}
    client, auth = client_with({"/api/v3/data/securitiesSummary": Pages([page1, page2])})
    client.login("none")
    rows = client.summaries("VN30", date(2026, 11, 4), date(2026, 11, 4))
    assert [r["symbol"] for r in rows] == ["FPT", "VNM"] and rows[0]["openPrice"] == 100
    assert rows[0]["foreignBuyValue"] is None and rows[1]["closePrice"] is None and rows[1]["invalid_fields"] == "closePrice"
    assert auth.rest_client.calls[0][1]["from"] == "2026/11/04" and auth.rest_client.calls[1][1]["pageIndex"] == 2
    with pytest.raises(NeoError):canonical_summary({"symbol": "", "tradingDate": "2026-11-04"}, "VN30")


def test_sdk_errors_become_safe_messages():
    from ssi_sdk.exceptions import AuthenticationError, RateLimitError
    for error, kind, text in ((AuthenticationError("SECRET"), AuthError, "từ chối"), (RateLimitError("SECRET"), NeoError, "429")):
        client, _ = client_with({"/api/v3/data/indexList": error})
        client.login("none")
        with pytest.raises(kind) as caught:
            client.get("indexList")
        assert text in str(caught.value) and "SECRET" not in str(caught.value)


# -- settings and connection contract ---------------------------------------------------------

def test_v3_settings_and_addresses(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("SSI_API_PROFILE=fastconnect_v3\nSSI_API_KEY=k\nSSI_API_SECRET=s\nSSI_OTP_MODE=smart\n", encoding="utf-8")
    monkeypatch.delenv("SSI_API_PROFILE", raising=False)
    settings = load_ssi_settings(env)
    assert settings.otp_mode == "smart" and settings.subscribe_mode == "index" and not settings.missing()
    monkeypatch.setenv("SSI_OTP_MODE", "sms")
    with pytest.raises(ConfigurationError):load_ssi_settings(env)
    with pytest.raises(ConfigurationError):SSISettings(profile="fastconnect_v3").validate_v3()
    assert v3_api_base() == "https://api.ssi.com.vn" == v3_api_base("https://api.ssi.com.vn/api/v3/")
    assert v3_stream_url() == "wss://stream.ssi.com.vn/ws/v3"
    for bad in ("http://api.ssi.com.vn", "https://evil.example/api/v3", "https://api.ssi.com.vn/api/v3?x=1"):
        with pytest.raises(ConfigurationError):v3_api_base(bad)
    with pytest.raises(ConfigurationError):v3_stream_url("ws://stream.ssi.com.vn/ws/v3")
    v3 = connection_plan("fastconnect_v3")["profiles"]["fastconnect_v3"]
    assert v3["stream_implemented"] and v3["rest_implemented"] and v3["sdk"] == "ssi-sdk==3.3.2"


# -- ops: reconciliation, history, smoke ---------------------------------------------------------

def test_reconcile_reports_ratios():
    stream = {"FPT": {"totalTradingVolume": 1000, "totalTradingValue": 2.02e8}, "XYZ": {"totalTradingVolume": 1}}
    rest = [{"symbol": "FPT", "index_group": "VN30", "totalTradingVolume": 1000, "totalTradingValue": 2e8,
             "foreignBuyValue": None, "foreignSellValue": None, "openPrice": None}]
    result = reconcile(stream, rest)
    assert result["summary"]["totalTradingVolume"]["median_ratio"] == 1
    assert result["summary"]["totalTradingValue"]["median_ratio"] == pytest.approx(1.01)
    assert result["summary"]["foreignBuyValue"]["symbols"] == 0 and len(result["rows"]) == 1


class HistoryClient:
    """Mirrors the live V3 behaviour seen 07/11/2026: ``index=`` returns the index itself,
    member rows come one symbol at a time."""
    login_mode = "none"

    def __init__(self, days):
        self.days = days

    def universe(self, groups=("VN30",)):
        return [{"symbol": f"{g[:3]}{i:02d}", "index_group": g, "marketCode": "HOSE"}
                for g in groups for i in range(12)]

    def member_summaries(self, members, start, end):
        rows = []
        for d, day in enumerate(self.days):
            for m in members:
                i = int(m["symbol"][-2:])
                rows.append({"symbol": m["symbol"], "index_group": m["index_group"], "tradingDate": day,
                             "openPrice": 100 + i, "closePrice": 100 + i + ((i + d) % 5 - 2), "totalTradingValue": 1e9 * (i + 1),
                             "foreignBuyValue": 1e7 * i, "foreignSellValue": 1e7 * (11 - i)})
        return rows

    def summaries(self, index, start, end):
        return [{"symbol": index, "index_group": index, "tradingDate": day, "openPrice": 1000.0, "closePrice": 1001.0,
                 "totalTradingValue": 1e12, "foreignBuyValue": None, "foreignSellValue": None} for day in self.days]


class BrokenList(HistoryClient):
    def universe(self, groups=("VN30",)):
        raise MemberListError("SSI trả chính chỉ số VN30 thay vì danh sách thành phần.")


def test_bad_list_reuses_the_last_complete_session_with_a_warning(tmp_path):
    db = tmp_path / "daily.sqlite"
    stored_days(db, 30, 29)
    with DailyStore(db) as store:  # a stray index row must never count as a member
        store.upsert("ssi", [{"symbol": "VN30", "index_group": "VN30", "tradingDate": "2026-11-01"}], "x")
    members, warning = resolve_members(BrokenList([]), database=db)
    assert len(members) == 30 and members[0] == {"symbol": "S00", "index_group": "VN30", "marketCode": "HOSE"}
    assert "2026-11-01" in warning and "VN30" not in {m["symbol"] for m in members}


def test_bad_list_without_a_stored_session_stops_before_writing(tmp_path):
    db = tmp_path / "daily.sqlite"
    with pytest.raises(MemberListError):history(V3_SETTINGS, BrokenList(["2026-11-02"]), sessions=5, database=db, today=date(2026, 11, 3))
    stored_days(db, 12)
    with pytest.raises(MemberListError):history(V3_SETTINGS, BrokenList(["2026-11-02"]), sessions=5, database=db, today=date(2026, 11, 3))
    with sqlite3.connect(db) as check:
        assert check.execute("SELECT COUNT(*) FROM daily_summary").fetchone()[0] == 12


def test_history_reports_the_fallback_and_stream_keeps_its_members(tmp_path, monkeypatch):
    db = tmp_path / "daily.sqlite"
    stored_days(db, 30)
    client = BrokenList(["2026-11-02"])
    client.member_summaries = lambda members, start, end: [
        {"symbol": m["symbol"], "index_group": "VN30", "tradingDate": "2026-11-02"} for m in members]
    result = history(V3_SETTINGS, client, sessions=5, database=db, today=date(2026, 11, 3))
    assert result["members"] == 30 and "dùng tạm" in result["member_warning"].lower()

    class Flaky(HistoryClient):
        calls = 0
        def universe(self, groups=("VN30",)):
            Flaky.calls += 1
            if Flaky.calls > 1:
                raise MemberListError("một dòng")
            return [{"symbol": "AAA", "index_group": "VN30", "marketCode": "HOSE"}]

    factory = V3Factory(Flaky([]))
    first = factory.bootstrap()
    assert factory.bootstrap() == first  # mid-run: no store lookup, no stop


def test_history_store_and_daily_evaluation(tmp_path):
    days = [f"2026-10-{d:02d}" for d in (26, 27, 28, 29, 30, 31)]
    result = history(V3_SETTINGS, HistoryClient(days), sessions=5, database=tmp_path / "daily.sqlite", today=date(2026, 11, 1))
    assert result["sessions"] == 5 and result["trading_dates"][0] == "2026-10-27" and result["rows"] == 60
    assert result["index_rows"] == 5 and set(result["rows_per_day"].values()) == {12}
    frame = read_daily(tmp_path / "daily.sqlite")
    evaluated = evaluate_daily(frame)
    vn = evaluated["groups"]["VN30"]
    assert evaluated["sessions"] == 5 and vn["day_to_day_persistence"]["turnover"]["mean_spearman"] == pytest.approx(1)
    with DailyStore(tmp_path / "daily.sqlite") as store:
        member = frame[frame["index_group"].eq("VN30")].drop(columns=["fetched_at", "source"])
        store.upsert("ssi", member.to_dict("records")[:1], now())
    assert len(read_daily(tmp_path / "daily.sqlite")) == 65  # 60 member rows + 5 index rows, upsert not duplicate


class SmokeClient(HistoryClient):
    def __init__(self, members):
        super().__init__([])
        self.members = members

    def universe(self, groups=("VN30",)):
        return [dict(m) for m in self.members]

    def summaries(self, index, start, end):
        return [{"symbol": m["symbol"], "index_group": index, "tradingDate": start.isoformat(), "present_fields": "close;open",
                 "totalTradingVolume": None, "totalTradingValue": None, "foreignBuyValue": None, "foreignSellValue": None,
                 "openPrice": None} for m in self.members if m["index_group"] == index]


def test_smoke_writes_evidence_without_secrets(tmp_path):
    members = v3_members(11)
    received = datetime.now(TZ)
    frames = baseline_frames(members, received)
    epoch_ms = int((received - timedelta(seconds=1)).timestamp() * 1000)
    raws = []
    for f in frames:
        raw = dict(f.raw)
        raw["data"] = {**raw["data"], "t": epoch_ms}
        raws.append(raw)
    client = SmokeClient(members)
    report = smoke(V3_SETTINGS, client, seconds=1, out_root=tmp_path / "evidence", today=received.date(),
                   database=tmp_path / "smoke.sqlite", ws_factory=lambda c: FakeWS(script=raws))
    profile = report["steps"]["stream_profile"]
    assert report["steps"]["universe"] == {"VN30": 11}
    assert profile["message_types"] == {"MARKET_FLAG": 1, "TRADE": 11, "QUOTE": 11, "ROOM": 11}
    assert profile["source_time_formats"]["TRADE"] == {"epoch_ms": 11}
    text = (tmp_path / "evidence").rglob("SMOKE.md").__next__().read_text(encoding="utf-8")
    assert "Smoke test FastConnect V3" in text and "api_secret" not in text.lower()


# -- CLI ------------------------------------------------------------------------------------------

def run_cli(monkeypatch, capsys, *argv):
    import sys
    from src import cli
    monkeypatch.setattr(sys, "argv", ["cli", *argv])
    code = cli.main()
    return code, capsys.readouterr().out


def test_cli_v3_readiness_and_missing_keys_stop_before_network(monkeypatch, capsys):
    monkeypatch.setenv("DATA_PROVIDER", "ssi")
    monkeypatch.setenv("SSI_API_PROFILE", "fastconnect_v3")
    monkeypatch.setenv("SSI_API_KEY", "")
    monkeypatch.setenv("SSI_API_SECRET", "")
    code, out = run_cli(monkeypatch, capsys, "readiness")
    data = json.loads(out)
    assert code == 0 and data["profile"] == "fastconnect_v3" and data["missing"] == ["SSI_API_KEY", "SSI_API_SECRET"]
    assert data["ssi_sdk_installed"] is True and data["network_called"] is False
    code, out = run_cli(monkeypatch, capsys, "smoke-v3", "--seconds", "5")
    assert code == 2 and "SSI_API_KEY" in out
    monkeypatch.setenv("SSI_API_PROFILE", "fcdata_v2")
    code, out = run_cli(monkeypatch, capsys, "history-v3")
    assert code == 2 and "fastconnect_v3" in out


def test_streamlit_replays_a_v3_journal_with_v3_warnings(monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest
    from src.config import PROJECT_ROOT
    path = tmp_path / "v3-ui.sqlite"
    collect_v3(path)
    monkeypatch.setenv("APP_MODE", "replay")
    monkeypatch.setenv("DATA_PROVIDER", "ssi")
    monkeypatch.setenv("SSI_DATABASE", str(path))
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    control = next(w for w in app.selectbox if w.label == "Mốc phát lại (UTC+7)")
    option = next(o for o in control.options if "10:00:30" in o)
    control.set_value(int(option.rsplit("#", 1)[1])).run()
    assert not app.exception
    table = app.dataframe[0].value
    assert table["Hạng"].notna().sum() == 11
    assert table["Cảnh báo"].str.contains("V3 không gửi trạng thái từng mã").all()


# Frames as received from the live stream on 09/11/2026 (public market data).
REAL_FRAMES = {
    "TRADE": {"data": {"a": "73354.24", "h": "74400", "l": "72700", "o": "73700", "p": "72900", "q": "100", "s": "MWG",
                       "t": "2026/11/09 13:15:40.198", "v": "1426700"}, "message_type": "TRADE", "topic": "trade.MWG"},
    "QUOTE": {"data": {"asks": [["57300", "36900"], ["57400", "14700"], ["57500", "7700"]] + [["0", "0"]] * 7,
                       "bids": [["57200", "34000"], ["57100", "63100"], ["57000", "73500"]] + [["0", "0"]] * 7,
                       "s": "VNM", "t": "2026/11/09 13:15:39"}, "message_type": "QUOTE", "topic": "quote.VNM"},
    "ROOM": {"data": {"bq": "450900", "bv": "9182840000", "cr": "463529303", "s": "ACB", "sq": "776400",
                      "sv": "15801840000", "t": "2026/11/09 13:16:00", "tr": "1741326587.0"},
             "message_type": "ROOM", "topic": "room.ACB"},
}


@pytest.mark.parametrize("kind", list(REAL_FRAMES))
def test_real_stream_frames_decode_with_their_source_time(kind):
    decoded = decode_v3(REAL_FRAMES[kind], received_at="2026-11-09T13:16:20+07:00")
    assert decoded["source_at"].startswith("2026-11-09T13:1"), decoded
    assert not {"SOURCE_TIME_UNAVAILABLE", "INVALID_OR_INCOMPLETE_SOURCE_TIME"} & {i["code"] for i in decoded["issues"]}
    assert decoded["message_type"] == kind


def test_real_trade_frame_keeps_milliseconds_and_derives_value():
    payload = decode_v3(REAL_FRAMES["TRADE"], received_at="2026-11-09T13:15:39.928+07:00")
    assert payload["source_at"].startswith("2026-11-09T13:15:40.198")
    assert float(payload["payload"]["closePrice"]) == 72900 and float(payload["payload"]["openPrice"]) == 73700
    assert float(payload["payload"]["totalTradingValue"]) == pytest.approx(73354.24 * 1426700)
