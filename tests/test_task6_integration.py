from copy import deepcopy
from io import BytesIO
import json

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.app.journal_view import snapshot_frame
from src.config import PROJECT_ROOT
from src.data.ssi_journal import SSIJournal
from src.finance.factors import factors
from src.ranking.engine import percentile, rank_groups, rank_snapshot
from src.ranking.verify_factors import hand_quote, verification_frame
from src.ssi_api.collect_sample import scenario
from src.ssi_api.replay import replay
from src.ssi_api.replay_sample import save_sample
from src.ssi_api.stream_collector import Frame, StreamAuthFailed, StreamDisconnected


def market_frame(kind, member, received, **values):
    content = {
        "Symbol": member["symbol"], "Exchange": member["marketCode"], "TradingDate": "04/11/2026",
        "Time": f"10:00:{received - 1:02d}", **values,
    }
    return Frame({"DataType": kind, "Content": content}, f"2026-11-04T10:00:{received:02d}+07:00")


def baseline(rows, received):
    messages = []
    for row in rows:
        quote = {
            "Open": row["openPrice"], "LastPrice": row["closePrice"],
            "TotalVal": row["totalTradingValue"], "TotalVol": row["totalTradingVolume"],
            "TradingSession": "LO", "TradingStatus": "N",
        }
        for side in ("Bid", "Ask"):
            for field in ("Price", "Vol"):
                for level in (1, 2, 3):
                    quote[f"{side}{field}{level}"] = row[f"{side.lower()}{field}{level}"]
        messages.append(market_frame("X", row, received, **quote))
        messages.append(market_frame("R", row, received, BuyVal=row["foreignBuyValue"],
                                     SellVal=row["foreignSellValue"], BuyVol=row["foreignBuyVolume"],
                                     SellVol=row["foreignSellVolume"]))
    return messages


@pytest.fixture(scope="module")
def market_journal(tmp_path_factory):
    frame = verification_frame()
    rows = frame.to_dict("records")
    members = frame[["symbol", "marketCode", "index_group"]].to_dict("records")
    probe = next(row for row in rows if row["symbol"] == "HOSETEST11")
    initial = baseline(rows, 1)
    duplicate = deepcopy(next(msg.raw for msg in initial if msg.raw["DataType"] == "R"
                              and msg.raw["Content"]["Symbol"] == probe["symbol"]))
    first = initial + [
        market_frame("X-TRADE", probe, 2, LastPrice=probe["closePrice"],
                     TotalVol=probe["totalTradingVolume"], TotalVal=probe["totalTradingValue"]),
        market_frame("X-TRADE", probe, 2, Time="09:59:59", LastPrice=1, TotalVol=1, TotalVal=1),
        Frame(duplicate, "2026-11-04T10:00:02+07:00"),
        market_frame("UNKNOWN", probe, 2, Private="SCHEMA_PRIVATE_SENTINEL"),
        market_frame("X-QUOTE", rows[0], 3, BidVol1=None),
        market_frame("X-QUOTE", rows[1], 3, BidVol1=None),
        StreamDisconnected(),
    ]
    second = [market_frame("X-TRADE", probe, 5, LastPrice=probe["closePrice"])]
    second.extend(baseline(rows, 6))
    second.append(StreamAuthFailed("AUTH_PRIVATE_SENTINEL"))
    path = tmp_path_factory.mktemp("task6") / "ssi-synthetic.sqlite"
    collected = save_sample(path, members, [first, second], seconds=20, max_messages=1000)
    with SSIJournal(path) as journal:
        events = list(journal.events(collected["run"]))
    return path, collected, events


def control(app, label):
    return next(widget for widget in app.selectbox if widget.label == label)


def at(app, events, *, second=None, state=None):
    if state:
        match = next(event for event in events if event["channel"] == "connection"
                     and event["payload"].get("state") == state)
    else:
        match = next(event for event in reversed(events) if event["channel"] == "ssiDecoded"
                     and event["received_at"][17:19] == f"{second:02d}")
    control(app, "Mốc phát lại (UTC+7)").set_value(match["event_id"]).run()
    assert not app.exception and not app.error
    return match["event_id"]


@pytest.fixture
def journal_app(monkeypatch, market_journal):
    path, _, _ = market_journal
    monkeypatch.setenv("APP_MODE", "replay")
    monkeypatch.setenv("DATA_PROVIDER", "ssi")
    monkeypatch.setenv("SSI_DATABASE", str(path))
    downloads = {}

    def capture(label, data, **kwargs):
        downloads[label] = data

    monkeypatch.setattr(st, "download_button", capture)
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception and not app.error
    return app, downloads


def csv_rows(downloads):
    return pd.read_csv(BytesIO(downloads["Tải bảng đang xem (CSV)"]))


def test_raw_ssi_to_ranked_ui_and_traceable_csv(market_journal, journal_app):
    _, collected, events = market_journal
    app, downloads = journal_app
    event_id = at(app, events, second=1)
    assert collected["network_called"] is False
    raw = [event for event in events if event["channel"] == "ssiRaw"]
    assert len(raw) == 94
    assert raw[0]["payload"]["message"]["Content"]["LastPrice"] == 19500
    table = app.dataframe[0].value
    assert len(table) == table["Hạng"].count() == 11
    probe = table.set_index("Mã").loc["HOSETEST11"]
    assert probe[["Động lượng", "Thanh khoản", "Dòng tiền ngoại", "Cung–cầu"]].tolist() == [100, 0, 100, 20]
    assert (probe["Điểm tổng"], probe["Hạng"]) == (55, 4)
    before = csv_rows(downloads).set_index("symbol").loc["HOSETEST11"]
    assert before["source"] == "synthetic" and before["run"] == collected["run"]
    assert before["event_id"] == event_id and before["cohort_size"] == 11
    assert before["method_version"] == "intraday-v1" and before["foreign_value_estimated"]

    app.multiselect[0].set_value(["HOSETEST11"]).run()
    assert not app.exception
    filtered = csv_rows(downloads)
    assert filtered["symbol"].tolist() == ["HOSETEST11"]
    assert filtered.loc[0, ["rank", "total_score", "cohort_id", "config_id"]].tolist() == [
        4, 55, before["cohort_id"], before["config_id"],
    ]
    control(app, "Trọng số").set_value("Ưu tiên động lượng 40/20/20/20").run()
    assert not app.exception
    updated = csv_rows(downloads).iloc[0]
    assert (updated["rank"], updated["total_score"], updated["weight_momentum"]) == (1, 64, 0.4)
    assert updated["config_id"] != before["config_id"] and updated["cohort_id"] == before["cohort_id"]


def test_ui_replays_null_gap_recovery_and_expired_auth(market_journal, journal_app):
    path, collected, events = market_journal
    app, downloads = journal_app
    assert collected["counters"] == dict(received=95, decoded=94, merged=92, duplicate=1,
                                         rejected=1, decode_errors=1, reconnects=1)
    assert "PRIVATE_SENTINEL" not in json.dumps(events)
    first_id = at(app, events, second=1)
    first_cohort = csv_rows(downloads)["cohort_id"].iloc[0]

    degraded_id = at(app, events, second=3)
    degraded = csv_rows(downloads)
    assert degraded["rank"].isna().all() and degraded["cohort_size"].eq(9).all()
    assert degraded["cohort_id"].ne(first_cohort).all()
    reasons = degraded.set_index("symbol")["quality_reason"]
    assert "Thiếu trường" in reasons.loc["HOSETEST01"] and "9/10" in reasons.loc["HOSETEST11"]
    report = replay(path, collected["run"], through_event_id=degraded_id)
    probe = next(row for row in report["rows"] if row["symbol"] == "HOSETEST11")
    assert probe["payload"]["closePrice"] == 20500 and probe["payload"]["totalTradingValue"] == 100_000_000
    assert probe["field_received_at"]["totalTradingValue"] == "2026-11-04T10:00:02+07:00"
    assert probe["field_received_at"]["foreignBuyValue"] == "2026-11-04T10:00:01+07:00"

    control(app, "Nhóm so sánh").set_value("HNX30").run()
    assert not app.exception
    assert app.dataframe[0].value["Hạng"].count() == 11
    at(app, events, state="disconnected")
    assert any("Mất kết nối" in notice.value for notice in app.warning)
    assert app.dataframe[0].value["Hạng"].isna().all()
    at(app, events, second=5)
    assert any("Đang chờ snapshot" in notice.value for notice in app.info)
    assert app.dataframe[0].value["Hạng"].isna().all()

    recovered_id = at(app, events, second=6)
    assert app.dataframe[0].value["Hạng"].count() == 11
    original = rank_groups(snapshot_frame(replay(path, collected["run"], through_event_id=first_id)))
    recovered = rank_groups(snapshot_frame(replay(path, collected["run"], through_event_id=recovered_id)))
    columns = ["symbol", "rank", "total_score", "cohort_id", "config_id"]
    pd.testing.assert_frame_equal(original[columns], recovered[columns])
    assert replay(path, collected["run"], through_event_id=recovered_id) == replay(
        path, collected["run"], through_event_id=recovered_id)
    at(app, events, state="auth_failed")
    assert any("Xác thực thất bại" in notice.value for notice in app.warning)
    assert app.dataframe[0].value["Hạng"].isna().all()


def test_unexpected_sdk_failure_closes_current_epoch_without_old_snapshot(tmp_path):
    members, scripts = scenario()
    path = tmp_path / "sdk-failure.sqlite"
    frames = scripts[0][:2] + [RuntimeError("SDK_PRIVATE_SENTINEL")]
    collected = save_sample(path, members, [frames])
    assert collected["stop_reason"] == "adapter_error" and collected["counters"]["reconnects"] == 0
    result = replay(path, collected["run"])
    assert result["last_recorded_connection_state"] == "adapter_error"
    assert all(not row["payload"] and not row["data_usable"] for row in result["rows"])
    with SSIJournal(path) as journal:
        assert "SDK_PRIVATE_SENTINEL" not in json.dumps(list(journal.events(collected["run"])))


def test_original_matrix_exact_arithmetic():
    assert percentile(pd.Series([1, 2, 3])).tolist() == [0, 50, 100]
    quote = {**hand_quote(), "closePrice": 102, "totalTradingValue": 200, "foreignBuyValue": 30,
             "foreignSellValue": 10, "askVol3": 200}
    row = factors(quote)
    assert [row[key] for key in ("momentum", "spread_bps", "imbalance", "foreign_net_vnd",
                                 "foreign_ratio", "depth_vnd")] == pytest.approx([2, 200, 0.2, 20, 0.1, 99700])

    # Spread and depth tie at 50. Turnover percentile 80 gives liquidity 60.
    rows = []
    for i in range(11):
        turnover = 200 + 10*i
        book_order = (i + 5) % 11
        row = {**quote, "symbol": f"ARITH{i:02d}", "source": "synthetic",
               "as_of": "2026-11-04T10:00:01+07:00", "quality_reason": "",
               "closePrice": 100 + i, "totalTradingValue": turnover,
               "foreignBuyValue": turnover * (((i + 7) % 11) + 5) / 100, "foreignSellValue": turnover / 10}
        for level in (1, 2, 3):
            row[f"bidPrice{level}"] = row[f"askPrice{level}"] = 100
            row[f"bidVol{level}"] = 150 + 10*book_order
            row[f"askVol{level}"] = 250 - 10*book_order
        rows.append(row)
    selected = rank_snapshot(pd.DataFrame(rows)).set_index("symbol").loc["ARITH08"]
    assert selected[["score_momentum", "score_liquidity", "score_foreign", "score_imbalance"]].tolist() == [80, 60, 40, 20]
    assert selected["total_score"] == 50
    tied = pd.DataFrame([{**rows[0], "symbol": "TIEB"}, {**rows[0], "symbol": "TIEA"}])
    tied_scores = rank_snapshot(tied, min_cohort=2)
    assert tied_scores["symbol"].tolist() == ["TIEA", "TIEB"]
    assert tied_scores["total_score"].tolist() == [50, 50] and tied_scores["rank"].tolist() == [1, 1]
