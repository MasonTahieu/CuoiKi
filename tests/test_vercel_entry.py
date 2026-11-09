"""Vercel entry (api/index.py), daily-store path override and deployment files. Offline."""
from http.server import ThreadingHTTPServer
import importlib.util
import json
import threading
import urllib.request

import pytest

from src.config import PROJECT_ROOT
from src.data.daily_store import DailyStore, default_daily_path
from src.data.store import now
from src.web import api


def load_entry():
    spec = importlib.util.spec_from_file_location("vercel_entry", PROJECT_ROOT / "api" / "index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("raw,expected", [
    ("/api/index?__path=/", "/"),
    ("/api/index?__path=/api/snapshot&source=daily&g=VN30", "/api/snapshot?source=daily&g=VN30"),
    ("/api/index?__path=app.css", "/app.css"),
    ("/api/context", "/api/context"),
])
def test_original_path_is_recovered_from_the_rewrite(raw, expected):
    assert load_entry().original_path(raw) == expected


def test_daily_path_follows_environment(monkeypatch, tmp_path):
    monkeypatch.delenv("SSI_DAILY_DATABASE", raising=False)
    assert default_daily_path() == PROJECT_ROOT / "runtime" / "ssi_daily.sqlite"
    monkeypatch.setenv("SSI_DAILY_DATABASE", "webdata/ssi_daily.sqlite")
    assert default_daily_path() == PROJECT_ROOT / "webdata" / "ssi_daily.sqlite"
    monkeypatch.setenv("SSI_DAILY_DATABASE", str(tmp_path / "x.sqlite"))
    assert default_daily_path() == tmp_path / "x.sqlite"


@pytest.fixture
def vercel_server(monkeypatch, tmp_path):
    rows = [{"symbol": f"AAA{i:02d}", "index_group": "VN30", "tradingDate": "2026-11-06", "openPrice": 10_000 + i,
             "closePrice": 10_050 + 7 * i, "totalTradingValue": 1e9 * (i + 1), "foreignBuyValue": 1e7 * i,
             "foreignSellValue": 1e7 * (12 - i)} for i in range(12)]
    path = tmp_path / "daily.sqlite"
    with DailyStore(path) as store:
        store.upsert("ssi", rows, now())
    monkeypatch.setattr(api, "DAILY_DB", path)
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("DATA_PROVIDER", "ssi")
    monkeypatch.setenv("VERCEL", "1")  # read-only SQLite mode, as on the platform
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), load_entry().handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def get(url):
    with urllib.request.urlopen(url, timeout=20) as response:
        return response.status, response.headers.get("Content-Type"), response.read()


def test_rewritten_requests_serve_page_assets_and_daily_api(vercel_server):
    status, kind, body = get(vercel_server + "/api/index?__path=/")
    assert status == 200 and "text/html" in kind and b"/app.js" in body
    status, kind, _ = get(vercel_server + "/api/index?__path=/app.css")
    assert status == 200 and "text/css" in kind
    status, _, body = get(vercel_server + "/api/index?__path=/api/context")
    assert "daily" in [s["id"] for s in json.loads(body)["sources"]]
    status, _, body = get(vercel_server + "/api/index?__path=/api/snapshot&source=daily&compare=")
    data = json.loads(body)
    assert data["method_kind"] == "daily" and data["groups"]["VN30"]["ranked"] == 12


def test_deployment_files_keep_secrets_and_heavy_stacks_out():
    ignore = (PROJECT_ROOT / ".vercelignore").read_text(encoding="utf-8").split()
    assert {".env", "runtime/", "tests/", "src/app/", "app.py"} <= set(ignore)
    requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "streamlit" not in requirements and "pandas" in requirements
    config = json.loads((PROJECT_ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert config["rewrites"][0]["destination"].startswith("/api/index?__path=")
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ssi-daily.yml").read_text(encoding="utf-8")
    assert "secrets.SSI_API_KEY" in workflow and "SSI_DAILY_DATABASE: webdata/ssi_daily.sqlite" in workflow
    assert "!webdata/ssi_daily.sqlite" in (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")


def test_stream_workflow_commits_summaries_only():
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ssi-stream.yml").read_text(encoding="utf-8")
    assert "git add evidence/v3_sessions/stream/" in workflow and "upload-artifact" not in workflow
    assert "stream-window" in workflow and "secrets.SSI_API_KEY" in workflow and "cancel-in-progress: false" in workflow


def test_vercel_installs_the_same_runtime_and_ships_the_demo_data():
    """Vercel reads pyproject.toml before requirements.txt; both must list the same pins."""
    import tomllib
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    pins = [line.strip() for line in (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]
    assert sorted(project["dependencies"]) == sorted(pins)
    ignore = (PROJECT_ROOT / ".vercelignore").read_text(encoding="utf-8").split()
    assert "data_sample/" not in ignore and "pyproject.toml" not in ignore
    config = json.loads((PROJECT_ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert "data_sample/**" in config["functions"]["api/index.py"]["includeFiles"]
