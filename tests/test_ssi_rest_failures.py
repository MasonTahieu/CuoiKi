import pytest
import requests
from streamlit.testing.v1 import AppTest

from src.config import PROJECT_ROOT
from src.data.store import TZ
from src.neo_api.rest import AuthError, NeoError
from src.ssi_api import collector
from src.ssi_api.fake_stream import FakeClock
from src.ssi_api.rest import SSIClient
from src.ssi_api.settings import SSISettings


class Response:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self.body = body

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.closed = False

    def _request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return result

    def post(self, url, **kwargs):
        return self._request("POST", url, **kwargs)

    def get(self, url, **kwargs):
        return self._request("GET", url, **kwargs)

    def close(self):
        self.closed = True


def token():
    return Response(body={"status": 200, "data": {"accessToken": "TEST_TOKEN_SENTINEL"}})


def page(rows):
    return Response(body={"status": 200, "totalRecord": len(rows), "data": rows})


def settings_for(path):
    return SSISettings(profile="fcdata_v2", consumer_id="mock-id", consumer_secret="TEST_SECRET_SENTINEL", database=path)


@pytest.mark.parametrize("failure,detail", [
    (Response(429, {"detail": "PRIVATE_BODY_SENTINEL"}), "429"),
    (Response(503), "503"),
    (Response(403), "403"),
    (requests.ReadTimeout("PRIVATE_BODY_SENTINEL"), "Không nhận được phản hồi"),
    (Response(body=ValueError("PRIVATE_BODY_SENTINEL")), "JSON hợp lệ"),
    (Response(body={"status": 200, "unexpected": "PRIVATE_BODY_SENTINEL"}), "schema"),
    (page(["PRIVATE_BODY_SENTINEL"]), "bản ghi"),
], ids=["quota-429", "server-503", "permission-403", "timeout", "invalid-json", "unknown-envelope", "invalid-record"])
def test_fcdata_failures_stop_at_one_paced_read_without_leaking_body(tmp_path, failure, detail):
    clock = FakeClock()
    session = Session([token(), failure])
    client = SSIClient(settings_for(tmp_path / "unused.sqlite"), session, sleep=clock.sleep, clock=clock.monotonic)
    try:
        client.authenticate()
        with pytest.raises(NeoError, match=detail) as error:
            client.components("VN30")
    finally:
        client.close()
    assert "SENTINEL" not in str(error.value)
    assert [call[0] for call in session.calls] == ["POST", "GET"] and session.closed
    assert clock.value == 1
    assert all(call[2]["timeout"] == (5, 20) and not call[2]["allow_redirects"] for call in session.calls)


def test_http_401_invalidates_token_until_explicit_authentication(tmp_path):
    clock = FakeClock()
    session = Session([token(), Response(401), token(), page([])])
    client = SSIClient(settings_for(tmp_path / "unused.sqlite"), session, sleep=clock.sleep, clock=clock.monotonic)
    try:
        client.authenticate()
        with pytest.raises(AuthError, match="xác thực lại"):
            client.list_all("DailyStockPrice")
        with pytest.raises(AuthError, match="Chưa đăng nhập"):
            client.list_all("DailyStockPrice")
        assert len(session.calls) == 2
        client.authenticate()
        assert client.list_all("DailyStockPrice") == []
    finally:
        client.close()
    assert [call[0] for call in session.calls] == ["POST", "GET", "POST", "GET"]


def test_rest_daily_snapshot_stays_unranked_in_ui_even_when_verified(monkeypatch, tmp_path):
    from datetime import datetime

    db = tmp_path / "daily.sqlite"
    day = datetime.now(TZ).strftime("%d/%m/%Y")
    replies = [token()]
    daily = []
    for group, market in (("VN30", "HOSE"), ("HNX30", "HNX")):
        symbols = [f"{market}DAY{i:02d}" for i in range(10)]
        replies.append(page([{"IndexCode": group, "Exchange": market, "TotalSymbolNo": 10,
                              "IndexComponent": [{"StockSymbol": symbol} for symbol in symbols]}]))
        daily.append(page([{"Symbol": symbol, "Tradingdate": day, "Openprice": 100, "Closeprice": 102,
                            "Totalmatchval": 10000, "Foreignbuyvaltotal": 1500,
                            "Foreignsellvaltotal": 1000} for symbol in symbols]))
    session = Session(replies + daily)
    clock = FakeClock()
    monkeypatch.setattr(collector, "SSIClient", lambda settings: SSIClient(
        settings, session=session, sleep=clock.sleep, clock=clock.monotonic))
    report = collector.collect_rest(settings_for(db))
    assert report["daily_rows"] == 20 and report["four_factor_ready"] is False and session.closed
    monkeypatch.setenv("APP_MODE", "replay")
    monkeypatch.setenv("DATA_PROVIDER", "ssi")
    monkeypatch.setenv("SSI_DATABASE", str(db))
    monkeypatch.setenv("SSI_SEMANTICS_VERIFIED", "true")
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception and not app.error
    for group in ("VN30", "HNX30"):
        chooser = next(control for control in app.selectbox if control.label == "Nhóm so sánh")
        chooser.set_value(group).run()
        assert not app.exception
        table = app.dataframe[0].value
        assert len(table) == 10 and table["Hạng"].isna().all()
        assert table["Lý do chưa xếp hạng"].str.contains("bidPrice1").all()
