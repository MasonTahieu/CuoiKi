"""Kiểm tra ranh giới demo, tính toàn vẹn fixture và khởi động UI P2."""

import ipaddress
import socket

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.config import ConfigurationError, PROJECT_ROOT, load_settings
from src.data.demo import DEMO_LABEL, DemoDataError, latest_snapshot, load_demo


@pytest.fixture(autouse=True)
def isolated_demo(monkeypatch):
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("APP_TIMEZONE", "Asia/Ho_Chi_Minh")
    original_connect = socket.socket.connect
    original_create = socket.create_connection

    def check_loopback(address):
        host = address[0]
        if host == "localhost":
            return
        try:
            if ipaddress.ip_address(host).is_loopback:
                return
        except ValueError:
            pass
        raise AssertionError("P2 không được kết nối mạng ra ngoài.")

    def local_connect(sock, address):
        check_loopback(address)
        return original_connect(sock, address)

    def local_create(address, *args, **kwargs):
        check_loopback(address)
        return original_create(address, *args, **kwargs)

    # Windows asyncio dùng socketpair trên loopback để chạy bộ kiểm thử UI.
    monkeypatch.setattr(socket.socket, "connect", local_connect)
    monkeypatch.setattr(socket, "create_connection", local_create)


def test_fixture_is_explicitly_synthetic_and_timezone_aware():
    frame = load_demo()
    assert len(frame) == 12
    assert frame["symbol"].nunique() == 4
    assert frame["source"].eq("synthetic").all()
    assert str(frame["observed_at"].dt.tz) == "Asia/Ho_Chi_Minh"
    assert len(latest_snapshot(frame)) == 4


@pytest.mark.parametrize("change", ["source", "symbol", "time", "nan", "negative", "duplicate"])
def test_fixture_rejects_ambiguous_or_invalid_data(tmp_path, change):
    frame = load_demo()
    frame["observed_at"] = pd.Series(
        [value.isoformat() for value in frame["observed_at"]], dtype=object
    )
    if change == "source":
        frame.loc[0, "source"] = "neo"
    elif change == "symbol":
        frame.loc[0, "symbol"] = "FPT"
    elif change == "time":
        frame.loc[0, "observed_at"] = "2026-10-23T09:30:00"
    elif change == "nan":
        frame.loc[0, "price_vnd"] = None
    elif change == "negative":
        frame.loc[0, "price_vnd"] = -1
    elif change == "duplicate":
        frame = pd.concat([frame, frame.iloc[[0]]])
    path = tmp_path / "bad_fixture.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(DemoDataError):
        load_demo(path)


def test_invalid_mode_is_rejected_even_with_credentials(monkeypatch):
    monkeypatch.setenv("APP_MODE", "invalid")
    monkeypatch.setenv("NEO_ACCESS_TOKEN", "test-placeholder-not-a-secret")
    with pytest.raises(ConfigurationError, match="APP_MODE chỉ hỗ trợ"):
        load_settings()


def test_ui_starts_and_empty_filter_is_explained():
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert "DỮ LIỆU GIẢ LẬP" in app.warning[0].value
    assert len(app.dataframe[0].value) == 12
    app.multiselect[0].set_value(["DEMO02"]).run()
    assert not app.exception
    assert app.dataframe[0].value["Mã"].tolist() == ["DEMO02"]
    app.multiselect[0].set_value([]).run()
    assert not app.exception
    assert len(app.dataframe) == 1  # quality tab remains visible
    assert any("Chưa chọn mã" in message.value for message in app.info)


def test_ui_does_not_fall_back_to_demo_for_live_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_MODE", "live")
    monkeypatch.setenv("NEO_DATABASE", str(tmp_path / "missing.sqlite"))
    monkeypatch.setenv("SSI_DATABASE", str(tmp_path / "missing.sqlite"))
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert any("Chưa có kho dữ liệu" in error.value for error in app.error)
    assert not app.dataframe

