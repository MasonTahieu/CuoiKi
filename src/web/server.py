"""Local web server for the screener UI. Standard library only; binds to loopback.

python -m src.web.server [--port 8501]
"""
import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sqlite3
import sys
import traceback
from urllib.parse import parse_qs, urlsplit

from src.config import ConfigurationError
from src.web import api

STATIC = Path(__file__).resolve().parent / "static"
FILES = {"/": "index.html", "/app.css": "app.css", "/app.js": "app.js", "/favicon.svg": "favicon.svg",
         "/favicon.ico": "favicon.svg"}  # browsers ask for /favicon.ico regardless of <link rel=icon>
SAFE_ERRORS = (api.ApiError, ConfigurationError, ValueError, OSError, sqlite3.Error)


class Handler(BaseHTTPRequestHandler):
    server_version = "Screener/1.0"

    def log_message(self, fmt, *args):  # keep the console readable; errors are logged below
        pass

    def _send(self, status, body, content_type, extra=None):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status, payload):
        self._send(status, json.dumps(payload, ensure_ascii=False, allow_nan=False, default=str), "application/json; charset=utf-8")

    def do_GET(self):
        parts = urlsplit(self.path)
        query = {k: v[-1] for k, v in parse_qs(parts.query).items()}
        try:
            if parts.path in FILES:
                path = STATIC / FILES[parts.path]
                kind = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                if kind.startswith("text/") or kind in {"application/javascript", "image/svg+xml"}:
                    kind += "; charset=utf-8"
                return self._send(HTTPStatus.OK, path.read_bytes(), kind)
            if parts.path == "/api/context":
                return self._json(HTTPStatus.OK, api.context())
            if parts.path == "/api/runs":
                return self._json(HTTPStatus.OK, api.runs(query.get("source", "")))
            if parts.path == "/api/timeline":
                return self._json(HTTPStatus.OK, api.timeline(query.get("source", ""), query.get("run")))
            if parts.path == "/api/snapshot":
                return self._json(HTTPStatus.OK, api.snapshot(query.get("source", ""), query.get("run"), query.get("point"),
                                                              query.get("weights", "balanced"), query.get("foreign", "value"),
                                                              query.get("compare") or None))
            if parts.path == "/api/history":
                return self._json(HTTPStatus.OK, api.history(query.get("source", ""), query.get("run"), query.get("point"),
                                                             query.get("symbol", "")))
            if parts.path == "/api/export.csv":
                body = api.export_csv(query.get("source", ""), query.get("run"), query.get("point"), query.get("weights", "balanced"),
                                      query.get("foreign", "value"), query.get("group"), query.get("compare") or None)
                name = f"screener_{query.get('group') or 'all'}.csv"
                return self._send(HTTPStatus.OK, body, "text/csv; charset=utf-8",
                                  {"Content-Disposition": f'attachment; filename="{name}"'})
            return self._json(HTTPStatus.NOT_FOUND, {"error": "Không tìm thấy đường dẫn."})
        except SAFE_ERRORS as error:
            if isinstance(error, sqlite3.Error):
                message = "Không đọc được kho SQLite. Kiểm tra đúng tệp và cấu trúc dữ liệu."
            else:
                message = str(error) or "Yêu cầu không hợp lệ."
            return self._json(HTTPStatus.BAD_REQUEST, {"error": message})
        except Exception:  # never leak a traceback to the page; keep it in the console
            traceback.print_exc(file=sys.stderr)
            return self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Lỗi nội bộ khi xử lý dữ liệu. Xem cửa sổ dòng lệnh."})


def make_server(port=8501):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Bộ lọc VN30 & HNX30 — giao diện web cục bộ")
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args()
    server = make_server(args.port)
    print(f"Mở http://127.0.0.1:{server.server_address[1]}  (Ctrl+C để dừng)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
