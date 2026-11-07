"""Vercel Python function: the same handler as src/web/server.py behind one catch-all rewrite.

vercel.json rewrites every path to /api/index?__path=/<original path>, so the handler can
recover the path the visitor asked for whatever the platform puts in ``self.path``.
"""
from pathlib import Path
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.web.server import Handler  # noqa: E402


def original_path(raw):
    parts = urlsplit(raw)
    query = parse_qsl(parts.query, keep_blank_values=True)
    wanted = [value for key, value in query if key == "__path"]
    if not wanted:
        return raw
    rest = [(key, value) for key, value in query if key != "__path"]
    path = wanted[-1] if wanted[-1].startswith("/") else "/" + wanted[-1]
    return path + ("?" + urlencode(rest) if rest else "")


class handler(Handler):
    def do_GET(self):
        self.path = original_path(self.path)
        return super().do_GET()
