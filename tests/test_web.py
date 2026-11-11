"""Web UI back end: JSON payloads and the loopback HTTP server. Offline, synthetic data only."""
import json
import threading
import urllib.error
import urllib.request

import pytest

from src.ssi_api.v3_sample import save_v3_sample
from src.web import api
from src.web.server import make_server


@pytest.fixture(autouse=True)
def no_local_daily_store(monkeypatch, tmp_path):
    """Keep tests independent of a real runtime/ssi_daily.sqlite on this machine."""
    monkeypatch.setattr(api, "DAILY_DB", tmp_path / "no-daily.sqlite")


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("DATA_PROVIDER", "ssi")


def test_context_lists_both_demo_sources(demo):
    ctx = api.context()
    assert ctx["mode"] == "demo" and [s["id"] for s in ctx["sources"]] == ["demo-board", "demo-journal"]
    assert {w["id"] for w in ctx["weights"]} == {"balanced", "momentum"}


def test_demo_board_snapshot_ranks_each_group_and_explains_contributions(demo):
    data = api.snapshot("demo-board")
    assert data["synthetic"] and data["verified"] and data["connection"]["state"] == "demo" and data["connection"]["label"] == "Bảng điểm giả lập"
    assert set(data["groups"]) == {"VN30"}  # scope: VN30 only
    for name in ("VN30",):
        group = data["groups"][name]
        assert group["members"] == group["ranked"] == 12 and group["cohort_size"] == 12
        ranks = [row["rank"] for row in group["rows"]]
        assert ranks == sorted(ranks)
        for row in group["rows"]:
            assert sum(row["contributions"].values()) == pytest.approx(row["total"])
            assert row["status"]["kind"] == "ranked" and row["status"]["details"] == []
    tilted = api.snapshot("demo-board", weights="momentum")
    assert tilted["weights"]["values"]["momentum"] == 0.4
    with pytest.raises(api.ApiError):
        api.snapshot("demo-board", weights="bogus")
    with pytest.raises(api.ApiError):
        api.runs("nowhere")


def test_demo_journal_replays_v3_and_reports_disconnect_per_stock(demo):
    runs = api.runs("demo-journal")
    v3 = next(r["id"] for r in runs if r["label"].startswith("V3"))
    points = api.timeline("demo-journal", v3)
    latest = api.snapshot("demo-journal", v3)
    assert latest["profile"] == "fastconnect_v3" and latest["groups"]["VN30"]["ranked"] == 11
    assert "Nguồn không gửi trạng thái từng mã" in latest["groups"]["VN30"]["rows"][0]["warnings"]
    reconnecting = next(p["id"] for p in points if p["label"] == "Đang kết nối" and p["at"].endswith("10:00:31+07:00"))
    gap = api.snapshot("demo-journal", v3, reconnecting)
    rows = gap["groups"]["VN30"]["rows"]
    assert gap["groups"]["VN30"]["ranked"] == 0 and gap["connection"]["severity"] == "warn"
    assert {r["status"]["kind"] for r in rows} == {"disconnected"} and rows[0]["status"]["details"]
    history = api.history("demo-journal", v3, None, latest["groups"]["VN30"]["rows"][0]["symbol"])
    assert len(history["points"]) == 2


def test_compare_reports_rank_and_score_change_against_an_earlier_moment(demo):
    data = api.snapshot("demo-board", compare="prev")
    assert data["compare"]["as_of"] == "2026-10-26T09:35:00+07:00"
    previous = {r["symbol"]: r for r in api.snapshot("demo-board", point="2026-10-26T09:35:00+07:00")["groups"]["VN30"]["rows"]}
    for row in data["groups"]["VN30"]["rows"]:
        assert row["prev_rank"] == previous[row["symbol"]]["rank"]
        assert row["rank_change"] == row["prev_rank"] - row["rank"]
        assert row["total_change"] == pytest.approx(row["total"] - previous[row["symbol"]]["total"])
    assert api.snapshot("demo-board", compare="300")["compare"]["point"] == "2026-10-26T09:35:00+07:00"
    missing = api.snapshot("demo-board", compare="900")
    assert missing["compare"]["point"] is None and "rank_change" not in missing["groups"]["VN30"]["rows"][0]
    assert api.snapshot("demo-board")["compare"] is None
    with pytest.raises(api.ApiError):
        api.snapshot("demo-board", compare="7")


def test_compare_on_a_journal_uses_a_strictly_earlier_recorded_moment(demo):
    v3 = next(r["id"] for r in api.runs("demo-journal") if r["label"].startswith("V3"))
    data = api.snapshot("demo-journal", v3, compare="prev")
    assert data["compare"]["as_of"] < data["as_of"]
    assert data["compare"]["as_of"].endswith("10:00:30+07:00")
    leader = data["groups"]["VN30"]["rows"][0]
    assert leader["rank"] == 1 and leader["prev_rank"] == 4 and leader["rank_change"] == 3
    csv_text = api.export_csv("demo-journal", v3, compare="30", group="VN30")
    header = csv_text.lstrip("\ufeff").splitlines()[0].split(",")
    assert {"compare_as_of", "prev_rank", "rank_change", "total_change"} <= set(header)


def test_daily_source_ranks_three_factors_and_names_missing_foreign_data(demo, monkeypatch, tmp_path):
    from src.data.daily_store import DailyStore
    from src.data.store import now
    days = ["2026-11-05", "2026-11-06"]
    rows = []
    for d, day in enumerate(days):
        # Legacy HNX30 rows may still sit in an old store: they must not appear on the page.
        for group, prefix, size in (("VN30", "AAA", 14), ("HNX30", "BBB", 12)):
            for i in range(size):
                foreign_missing = group == "VN30" and i < 3
                rows.append({"symbol": f"{prefix}{i:02d}", "index_group": group, "tradingDate": day,
                             "openPrice": 10_000 + 100 * i, "closePrice": 10_000 + 100 * i + 50 * ((i + d) % 5 - 2),
                             "totalTradingValue": 1e9 * (i + 1 + d), "totalTradingVolume": 1e5 * (i + 1),
                             "foreignBuyValue": None if foreign_missing else 1e7 * i,
                             "foreignSellValue": None if foreign_missing else 1e7 * (11 - i),
                             "foreignBuyVolume": None, "foreignSellVolume": None})
    rows.append({"symbol": "VN30", "index_group": "INDEX", "tradingDate": days[-1], "openPrice": 1800.0, "closePrice": 1810.0,
                 "totalTradingValue": 7e12})
    path = tmp_path / "daily.sqlite"
    with DailyStore(path) as store:
        store.upsert("ssi", rows, now())
    monkeypatch.setattr(api, "DAILY_DB", path)
    sources = api.context()["sources"]
    assert [s["id"] for s in sources] == ["daily", "demo-board", "demo-journal"]
    assert all(s["label"].startswith("Minh họa · ") for s in sources[1:])
    assert [p["label"] for p in api.timeline("daily", "ssi-daily")] == ["Phiên 05/11/2026", "Phiên 06/11/2026"]
    data = api.snapshot("daily", compare="prev")
    assert data["method_kind"] == "daily" and data["source"] == "ssi" and data["compare"]["as_of"].startswith("2026-11-05")
    vn = data["groups"]["VN30"]
    assert set(data["groups"]) == {"VN30"}
    assert vn["members"] == 14 and vn["ranked"] == 11 and vn["method"] == "daily-v1"  # the INDEX row is not a member
    row = vn["rows"][0]
    assert row["scores"]["imbalance"] is None and row["contributions"]["imbalance"] is None
    assert sum(v for v in row["contributions"].values() if v is not None) == pytest.approx(row["total"])
    assert row["rank_change"] == row["prev_rank"] - row["rank"]
    missing = [r for r in vn["rows"] if r["rank"] is None]
    assert len(missing) == 3
    assert missing[0]["status"]["details"] == ["Thiếu dữ liệu khối ngoại (SSI trả trống)"]
    assert missing[0]["status"]["label"] == "Thiếu khối ngoại"
    assert missing[0]["total"] is None and missing[0]["raw"]["foreign_ratio"] is None
    assert missing[0]["raw"]["momentum"] == pytest.approx(-0.5)
    assert missing[0]["raw"]["turnover"] == 2e9
    assert data["pulse"]["total_value"] == sum(range(2, 16)) * 1e9
    assert [p["label"] for p in api.history("daily", "ssi-daily", None, "AAA03")["points"]] == ["05/11", "06/11"]
    with pytest.raises(api.ApiError):
        api.snapshot("daily", weights="bogus")


def test_csv_export_carries_configuration(demo):
    text = api.export_csv("demo-board", weights="momentum", group="VN30")
    assert text.startswith("\ufeff")
    lines = text.lstrip("\ufeff").splitlines()
    header = lines[0].split(",")
    assert {"config_id", "cohort_id", "weight_momentum", "foreign_basis"} <= set(header)
    assert len(lines) == 13 and all(",VN30," in line for line in lines[1:])


def test_replay_store_reads_a_saved_v3_journal(monkeypatch, tmp_path):
    path = tmp_path / "store.sqlite"
    collected = save_v3_sample(path)
    monkeypatch.setenv("APP_MODE", "replay")
    monkeypatch.setenv("DATA_PROVIDER", "ssi")
    monkeypatch.setenv("SSI_DATABASE", str(path))
    assert [s["id"] for s in api.context()["sources"]] == ["store"]
    assert [r["id"] for r in api.runs("store")] == [collected["run"]]
    data = api.snapshot("store", collected["run"])
    assert data["connection"]["state"] == "stopped" and data["groups"]["VN30"]["ranked"] == 0
    monkeypatch.setenv("SSI_DATABASE", str(tmp_path / "missing.sqlite"))
    assert api.context()["sources"] == []


@pytest.fixture
def server(demo):
    httpd = make_server(0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


def test_server_serves_static_files_json_and_safe_errors(server):
    status, headers, body = fetch(server + "/")
    assert status == 200 and "text/html" in headers["Content-Type"] and b"app.js" in body
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    status, headers, _ = fetch(server + "/app.js")
    assert status == 200 and "javascript" in headers["Content-Type"]
    status, _, body = fetch(server + "/api/snapshot?source=demo-board&weights=balanced")
    assert status == 200 and json.loads(body)["groups"]["VN30"]["ranked"] == 12
    status, _, body = fetch(server + "/api/snapshot?source=demo-board&weights=bad")
    assert status == 400 and "trọng số" in json.loads(body)["error"]
    status, _, _ = fetch(server + "/../src/config.py")
    assert status == 404
    status, headers, body = fetch(server + "/api/export.csv?source=demo-board&group=VN30")
    assert status == 200 and "attachment" in headers["Content-Disposition"] and body.startswith(b"\xef\xbb\xbf")


def test_favicon_is_served_for_both_paths(server):
    for path in ("/favicon.svg", "/favicon.ico"):
        with urllib.request.urlopen(server + path, timeout=20) as response:
            assert response.status == 200 and response.headers.get("Content-Type").startswith("image/svg+xml")
