from copy import deepcopy
import json
import pandas as pd
import pytest
import requests

from src.config import ConfigurationError
from src.neo_api.settings import NeoSettings
from src.neo_api.rest import RestClient, NeoError, AuthError
from src.neo_api.stream import decode_message, subscriptions
from src.data.store import EventStore, read_events
from src.data.synthetic import demo_events
from src.data.normalize import state_at, recorded_update_mode
from src.finance.factors import factors
from src.ranking.engine import rank_snapshot, percentile


class Response:
    def __init__(self, body=None, status=200, headers=None):
        self.status_code, self.body, self.headers = status, body, headers or {}
    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


class Session:
    def __init__(self, responses):
        self.responses, self.calls = iter(responses), []
    def get(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        item = next(self.responses)
        if isinstance(item, Exception):
            raise item
        return item
    def close(self):
        pass


def client(responses):
    session, sleeps = Session(responses), []
    settings = NeoSettings(token="SECRET_SENTINEL", device="test")
    return RestClient(settings, session=session, sleep=sleeps.append, clock=lambda:0), session, sleeps


def page(rows, pages=2, total=2):
    return Response({"status":1,"data":{"content":rows,"totalPages":pages,"totalElements":total}})


def member(symbol):
    return {"symbol":symbol, "marketCode":"HOSE", "stockType":"ST"}


def test_rest_reads_every_page_with_safe_headers_and_spacing():
    api, session, sleeps = client([page([member("A")]), page([member("B")])])
    assert [r["symbol"] for r in api.vn30()] == ["A", "B"]
    assert [c[1]["params"]["pageNo"] for c in session.calls] == [1,2]
    assert all(c[1]["allow_redirects"] is False for c in session.calls)
    assert session.calls[0][1]["headers"]["Authorization"] == "Bearer SECRET_SENTINEL"
    assert 0.3 in sleeps


@pytest.mark.parametrize("responses", [
    [page([member("A")]),page([member("A")])],
    [page([member("A")],1,2)],
    [page([member("A")]),page([member("B")],3,3)],
    [Response({"status":1,"data":[]})],
])
def test_bad_pagination_never_returns_partial_universe(responses):
    api, _, _ = client(responses)
    with pytest.raises(NeoError):
        api.vn30()


@pytest.mark.parametrize("status", [401,403])
def test_auth_failure_does_not_retry_or_leak_body(status):
    api, session, _ = client([Response({"message":"SECRET_SENTINEL"},status)])
    with pytest.raises(AuthError) as error:
        api.get("stock_list")
    assert len(session.calls) == 1
    assert "SECRET_SENTINEL" not in str(error.value)
    assert "SECRET_SENTINEL" not in repr(api.settings)


def test_retry_after_server_failure_and_timeout_are_bounded():
    api, session, sleeps = client([Response(status=429,headers={"Retry-After":"3"}),
        requests.Timeout("SECRET_SENTINEL"),Response({"status":1,"data":[]})])
    assert api.get("market_status")["data"] == []
    assert len(session.calls) == 3 and 3 in sleeps
    api, session, _ = client([Response(status=503)]*3)
    with pytest.raises(NeoError):
        api.get("market_status")
    assert len(session.calls) == 3


@pytest.mark.parametrize("response", [Response({},302), Response({"status":0,"message":"SECRET_SENTINEL"}),Response(ValueError())])
def test_unsafe_or_invalid_response_is_rejected(response):
    api, _, _ = client([response])
    with pytest.raises(NeoError) as error:
        api.get("vn30")
    assert "SECRET_SENTINEL" not in str(error.value)


def test_trading_endpoint_not_allowed():
    api, session, _ = client([])
    with pytest.raises(NeoError):
        api.get("/trading/placeOrder")
    assert not session.calls


@pytest.mark.parametrize("url", ["", "ws://neoapi.vpbanks.com.vn/stock-stream/broker", "wss://example.com/stock-stream/broker", "wss://neoapi.vpbanks.com.vn/trading-stream/broker", "wss://neoapi.vpbanks.com.vn/stock-stream/broker?token=x"])
def test_insecure_or_wrong_websocket_target_rejected(url):
    with pytest.raises(ConfigurationError):
        NeoSettings(token="x",device="x",ws_url=url).validate(websocket=True)


def test_protocol_auth_and_market_envelopes():
    assert decode_message('{"type":"auth","status":"success","data":{"username":"private"}}') == ("auth",{})
    with pytest.raises(AuthError):
        decode_message('{"type":"auth","status":"error","data":"private"}')
    assert decode_message('{"symbol":"DEMO01","closePrice":12}')[0] == "stockInfo"
    assert decode_message('{"channel":"stockInfo","data":{"symbol":"A"}}', "channel_data")[0] == "stockInfo"
    with pytest.raises(NeoError):
        decode_message('{"unknown":"x"}')
    assert subscriptions(["A"])[0]["listId"] == ["A"]


def test_store_replay_is_idempotent_and_keeps_sources_separate(tmp_path):
    path = tmp_path / "test.sqlite"
    store = EventStore(path)
    for _ in range(2):
        for event in demo_events():
            store.append(**event)
    store.append("neo","other","2026-10-26T10:00:00+07:00","connection",{"state":"connected","access_token":"SECRET"})
    store.close()
    events = read_events(path,"synthetic-v1")
    assert len(events) == 38
    pd.testing.assert_frame_equal(state_at(events), state_at(demo_events()))
    assert "access_token" not in read_events(path,"other")[0]["payload"]


def test_replay_has_no_lookahead_and_stale_data_not_ranked():
    events = demo_events()
    frame = state_at(events,"2026-10-26T09:30:00+07:00")
    assert frame["received_at"].eq("2026-10-26T09:30:00+07:00").all()
    assert rank_snapshot(frame)["rank"].notna().sum() == 12
    late = rank_snapshot(state_at(events,"2026-10-26T09:42:00+07:00"))
    assert late["rank"].isna().all()
    assert late["quality_reason"].str.contains("cũ").all()


def test_patch_missing_keeps_previous_but_null_invalidates_and_field_age_persists():
    events = demo_events()[:14]
    event = dict(source="synthetic", run="synthetic-v1",received_at="2026-10-26T09:30:10+07:00",
        channel="stockInfo", payload={"symbol":"DEMO01","closePrice":20001})
    events.append(event)
    patch = state_at(events,update_mode="patch").set_index("symbol")
    assert patch.loc["DEMO01","openPrice"] == 20000
    assert patch.loc["DEMO01","quality_reason"] == ""
    snapshot = state_at(events).set_index("symbol")
    assert "thiếu" in snapshot.loc["DEMO01","quality_reason"]
    event["payload"]["openPrice"] = None
    patch = state_at(events,update_mode="patch").set_index("symbol")
    assert pd.isna(patch.loc["DEMO01","openPrice"])
    assert "thiếu" in patch.loc["DEMO01","quality_reason"]
    del event["payload"]["openPrice"]
    event["received_at"] = "2026-10-26T09:31:30+07:00"
    assert "cũ" in state_at(events,update_mode="patch").set_index("symbol").loc["DEMO01","quality_reason"]


def test_late_update_does_not_overwrite_newer_and_disconnect_clears_state():
    events = demo_events()
    stale = deepcopy(events[2])
    stale["payload"]["closePrice"] = 1
    events.append(stale)
    frame = state_at(events).set_index("symbol")
    assert frame.loc["DEMO01","closePrice"] != 1
    events.append(dict(source="synthetic",run="synthetic-v1",received_at="2026-10-26T09:40:01+07:00",channel="connection",payload={"state":"disconnected"}))
    assert state_at(events).empty


@pytest.mark.parametrize("field,value", [("bidPrice1","ATO"),("askPrice1","ATC"),("openPrice",0),
    ("foreignBuyValue",None),("bidVol1",-10),("closePrice","bad"),("askPrice1",1),
    ("totalTradingValue",0),("tradingStatus","HALT")])
def test_bad_quotes_excluded_without_reweighting(field,value):
    events = demo_events()
    events[-1]["payload"][field] = value
    row = rank_snapshot(state_at(events)).set_index("symbol").loc["DEMO12"]
    assert pd.isna(row["rank"]) and row["quality_reason"]


def test_foreign_counter_rollback_and_auction_session_are_excluded():
    events = demo_events()
    events[-1]["payload"]["foreignBuyValue"] = 1
    assert "cộng dồn giảm" in state_at(events).set_index("symbol").loc["DEMO12","quality_reason"]
    events[1]["payload"]["marketStatus"] = "ATC"
    assert rank_snapshot(state_at(events))["rank"].isna().all()


def test_real_data_scoring_needs_explicit_semantic_verification():
    frame = state_at(demo_events())
    frame["source"] = "neo"
    assert rank_snapshot(frame)["rank"].isna().all()
    assert rank_snapshot(frame,semantics_verified=True)["rank"].notna().all()


def test_hand_calculated_factors_and_average_ties():
    row = state_at(demo_events()).iloc[0].to_dict()
    row.update(closePrice=110,openPrice=100,totalTradingValue=10000,foreignBuyValue=3000,foreignSellValue=1000)
    for i in (1,2,3):
        row[f"bidPrice{i}"], row[f"askPrice{i}"] = 100-i,100+i
        row[f"bidVol{i}"], row[f"askVol{i}"] = 200,100
    result = factors(row)
    assert result["momentum"] == pytest.approx(10)
    assert result["foreign_ratio"] == pytest.approx(0.2)
    assert result["imbalance"] == pytest.approx(1/3)
    assert result["depth_vnd"] == 89400
    assert result["spread_bps"] == 200
    assert percentile(pd.Series([1,2,2,4])).tolist() == [0,50,50,100]
    assert percentile(pd.Series([5,5,5])).tolist() == [50,50,50]
    assert percentile(pd.Series([1,2,3]),False).tolist() == [100,50,0]


def test_small_cohort_weights_and_configuration_trace():
    frame = state_at(demo_events())
    assert rank_snapshot(frame.iloc[:9])["rank"].isna().all()
    base = rank_snapshot(frame)
    varied = rank_snapshot(frame,weights=dict(momentum=.4,liquidity=.2,foreign=.2,imbalance=.2))
    assert base["total_score"].between(0,100).all()
    tied = base.set_index("symbol")
    assert tied.loc["DEMO07","rank"] == tied.loc["DEMO08","rank"]
    assert base["config_id"].iloc[0] != varied["config_id"].iloc[0]
    assert base["cohort_id"].iloc[0] == varied["cohort_id"].iloc[0]
    with pytest.raises(ValueError):
        rank_snapshot(frame,weights=dict(momentum=1,liquidity=1,foreign=1,imbalance=1))
    with pytest.raises(ValueError):
        rank_snapshot(pd.concat([frame, frame.iloc[:1]]))


def test_replay_uses_recorded_mode_and_rejects_inconsistent_run():
    events = demo_events()
    marker = dict(source="synthetic",run="synthetic-v1",received_at="2026-10-26T09:30:00+07:00",
                  channel="connection",payload={"state":"connected","update_mode":"patch"})
    events.append(marker)
    assert recorded_update_mode(events,"snapshot") == "patch"
    other = deepcopy(marker)
    other["payload"]["update_mode"] = "snapshot"
    events.append(other)
    with pytest.raises(ValueError):
        recorded_update_mode(events)
