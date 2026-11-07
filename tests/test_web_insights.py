"""Market pulse, rank-history heatmap and validation endpoints of the web API. Offline."""
import json
import threading
import urllib.error
import urllib.request

import pytest

from src.data.daily_store import DailyStore
from src.data.store import now
from src.web import api
from src.web.server import make_server

DAYS = ["2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06"]


@pytest.fixture
def daily(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("DATA_PROVIDER", "ssi")
    rows = []
    for d, day in enumerate(DAYS):
        for i in range(12):
            change = (i - 5) * 0.5 if d % 2 == 0 else (5 - i) * 0.5  # flips every session
            rows.append({"symbol": f"S{i:02d}", "index_group": "VN30", "tradingDate": day,
                         "openPrice": 10_000, "closePrice": 10_000 + 20 * i, "totalTradingValue": 1e9 * (i + 1),
                         "foreignBuyValue": None if (i == 0 and d == 1) else 1e7 * i, "foreignSellValue": 5e7,
                         "priceChangePercent": change})
        rows.append({"symbol": "VN30", "index_group": "INDEX", "tradingDate": day, "closePrice": 1800 + d,
                     "priceChange": 1.0 + d, "priceChangePercent": 0.1 * (d + 1), "totalTradingValue": 7e12})
    path = tmp_path / "daily.sqlite"
    with DailyStore(path) as store:
        store.upsert("ssi", rows, now())
    monkeypatch.setattr(api, "DAILY_DB", path)
    return path


def test_daily_pulse_uses_reference_breadth_index_and_foreign_net(daily):
    pulse = api.snapshot("daily")["pulse"]
    assert pulse["basis"] == "tham chiếu" and pulse["members"] == pulse["priced"] == 12
    # last session (d=3) flips: change = (5 - i) * 0.5 -> 5 up (i<5), 1 flat (i=5), 6 down
    assert (pulse["advancers"], pulse["unchanged"], pulse["decliners"]) == (5, 1, 6)
    assert pulse["total_value"] == pytest.approx(sum(1e9 * (i + 1) for i in range(12)))
    assert pulse["foreign_net"] == pytest.approx(sum(1e7 * i - 5e7 for i in range(12)))
    assert pulse["index"] == {"close": 1803, "change": 4.0, "change_pct": pytest.approx(0.4), "value": 7e12}


def test_intraday_pulse_falls_back_to_change_since_open(daily):
    pulse = api.snapshot("demo-board")["pulse"]
    assert pulse["basis"] == "giá mở cửa" and pulse["index"] is None
    assert pulse["advancers"] + pulse["decliners"] + pulse["unchanged"] == pulse["priced"] == 12


def test_heatmap_ranks_every_session_and_names_the_gap(daily):
    h = api.heatmap("daily")
    assert [d["label"] for d in h["days"]] == ["03/11", "04/11", "05/11", "06/11"]
    assert len(h["rows"]) == 12 and h["rows"][0]["latest"] == 1
    gap = next(r for r in h["rows"] if r["symbol"] == "S00")
    assert gap["ranks"][1] is None and "khối ngoại" in gap["reasons"]["1"] and gap["ranked_sessions"] == 3
    assert [r["latest"] for r in h["rows"]] == sorted(r["latest"] for r in h["rows"])
    with pytest.raises(api.ApiError, match="Cuối ngày"):
        api.heatmap("demo-board")
    with pytest.raises(api.ApiError):
        api.heatmap("daily", weights="bogus")


def test_validation_reports_the_chosen_weights_honestly(daily):
    v = api.validation("daily", "momentum")
    assert v["weights"] == "momentum" and v["sessions"] == 4 and v["pairs"] == 3 and len(v["series"]) == 3
    assert set(v["factor_ic"]) == {"momentum", "liquidity", "foreign"}
    assert v["verdict"] and v["summary"]["ic"]["pairs"] == 3
    with pytest.raises(api.ApiError, match="Cuối ngày"):
        api.validation("demo-journal")


def test_server_routes_return_json_and_safe_errors(daily):
    httpd = make_server(0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        for path in ("/api/heatmap?source=daily", "/api/validation?source=daily&weights=balanced"):
            with urllib.request.urlopen(base + path, timeout=20) as response:
                json.loads(response.read())
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(base + "/api/heatmap?source=demo-board", timeout=20)
        assert error.value.code == 400 and "Cuối ngày" in json.loads(error.value.read())["error"]
    finally:
        httpd.shutdown()
        httpd.server_close()
