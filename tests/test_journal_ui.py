from io import BytesIO

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.config import PROJECT_ROOT
from src.data.store import EventStore
from src.ssi_api.collect_sample import scenario
from src.ssi_api.replay_sample import save_sample, stale_scenario


def start_app(monkeypatch, mode, database=None):
    monkeypatch.setenv("APP_MODE", mode)
    monkeypatch.setenv("DATA_PROVIDER", "ssi")
    if database:
        monkeypatch.setenv("SSI_DATABASE", str(database))
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    return app


def widget(app, label):
    return next(control for control in app.selectbox if control.label == label)


def select_moment(app, text):
    control = widget(app, "Mốc phát lại (UTC+7)")
    match = next(option for option in control.options if text in option)
    control.set_value(int(match.rsplit("#", 1)[1])).run()
    assert not app.exception


def test_sample_demo_replay_distinguishes_disconnect_and_stock_halt(monkeypatch):
    app = start_app(monkeypatch, "demo")
    app.radio[0].set_value("Nhật ký SSI mẫu").run()
    assert not app.exception
    assert app.dataframe[0].value.loc[0, "Cảnh báo"] == "Giá trị ngoại ước tính"
    widget(app, "Nhóm so sánh").set_value("HNX30").run()
    hnx = app.dataframe[0].value.iloc[0]
    assert hnx["Mã"] == "HNDEMO01"
    assert "trạng thái giao dịch bình thường" in hnx["Lý do chưa xếp hạng"]

    select_moment(app, "10:00:06 · Mất kết nối")
    assert any("Kết nối tại mốc chọn · Mất kết nối" in notice.value for notice in app.warning)
    assert any("Đang chờ snapshot" in notice.value for notice in app.info)
    assert app.dataframe[0].value["Hạng"].isna().all()
    select_moment(app, "10:00:00 · Đang kết nối")
    assert not app.dataframe
    assert any("Đang chờ snapshot" in notice.value for notice in app.info)


def test_saved_replay_run_selector_exposes_stale_age_and_csv_metadata(monkeypatch, tmp_path):
    database = tmp_path / "ssi-demo.sqlite"
    first = save_sample(database, *scenario())
    second = save_sample(database, *stale_scenario(), seconds=65, max_messages=100)
    downloads = {}

    def capture_download(label, data, **kwargs):
        downloads[label] = data

    monkeypatch.setattr(st, "download_button", capture_download)
    app = start_app(monkeypatch, "replay", database)
    assert widget(app, "Lần thu thập").value == second["run"]
    assert any("Đã dừng thu thập" in notice.value for notice in app.warning)
    select_moment(app, "10:01:03 · Dữ liệu cổ phiếu")
    quality = next(table.value for table in app.dataframe if "Khối ngoại (s)" in table.value.columns)
    assert quality.loc[0, "Khối ngoại (s)"] == "63"
    assert "Trường quá cũ" in quality.loc[0, "Lý do chưa xếp hạng"]

    widget(app, "Lần thu thập").set_value(first["run"]).run()
    assert not app.exception
    select_moment(app, "10:00:13 · Dữ liệu cổ phiếu")
    widget(app, "Trọng số").set_value("Ưu tiên động lượng 40/20/20/20").run()
    exported = pd.read_csv(BytesIO(downloads["Tải bảng đang xem (CSV)"]))
    row = exported.iloc[0]
    assert row["run"] == first["run"] and row["source"] == "synthetic" and row["index_group"] == "VN30"
    assert row["method_version"] == "intraday-v1" and row["event_id"] == widget(app, "Mốc phát lại (UTC+7)").value
    assert [row[f"weight_{name}"] for name in ("momentum", "liquidity", "foreign", "imbalance")] == [0.4, 0.2, 0.2, 0.2]
    assert row["foreign_value_estimated"]


def test_live_rejects_sample_store_and_refresh_reads_new_connection_record(monkeypatch, tmp_path):
    database = tmp_path / "ssi-demo.sqlite"
    save_sample(database, *scenario())
    app = start_app(monkeypatch, "live", database)
    assert any("lần thu thập SSI thật" in error.value for error in app.error)
    assert not app.dataframe
    assert widget(app, "Tự làm mới kho").value == 0

    # Create only a connection marker for the SSI branch. No market data or credentials.
    from src.data.store import now
    store = EventStore(database)
    try:
        store.append("ssi", "ssi-test", now(), "connection", {"state": "connecting", "connection_epoch": 1})
    finally:
        store.close()
    next(button for button in app.button if button.label == "Đọc lại kho dữ liệu").click().run()
    assert not app.exception and not app.error
    assert any("Trạng thái ghi gần nhất · Đang kết nối" in notice.value for notice in app.info)
    assert any("Đang chờ snapshot" in notice.value for notice in app.info)
