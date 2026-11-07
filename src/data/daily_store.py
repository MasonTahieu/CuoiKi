"""Daily securitiesSummary rows (FastConnect V3 REST), one row per symbol/group/trading day.

Kept apart from the intraday event journal: daily totals are end-of-day context and are never
merged into the intraday order-book state.
"""
import json
import os
from pathlib import Path
import sqlite3

import pandas as pd

from src.config import PROJECT_ROOT


def default_daily_path():
    """runtime/ssi_daily.sqlite locally; SSI_DAILY_DATABASE (relative to the project) on CI/Vercel."""
    value = os.environ.get("SSI_DAILY_DATABASE", "").strip()
    path = Path(value) if value else PROJECT_ROOT / "runtime" / "ssi_daily.sqlite"
    return path if path.is_absolute() else PROJECT_ROOT / path


class DailyStore:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10)
        self.db.execute("""CREATE TABLE IF NOT EXISTS daily_summary (
            source TEXT NOT NULL, symbol TEXT NOT NULL, index_group TEXT NOT NULL, trading_date TEXT NOT NULL,
            fetched_at TEXT NOT NULL, payload TEXT NOT NULL,
            PRIMARY KEY (source, symbol, index_group, trading_date))""")
        self.db.commit()

    def upsert(self, source, rows, fetched_at):
        if source not in {"ssi", "synthetic"}:
            raise ValueError("Nguồn dữ liệu ngày không được hỗ trợ.")
        with self.db:
            for row in rows:
                self.db.execute("""INSERT INTO daily_summary(source,symbol,index_group,trading_date,fetched_at,payload)
                    VALUES(?,?,?,?,?,?) ON CONFLICT(source,symbol,index_group,trading_date)
                    DO UPDATE SET fetched_at=excluded.fetched_at, payload=excluded.payload""",
                    (source, row["symbol"], row["index_group"], row["tradingDate"], fetched_at,
                     json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False)))
        return len(rows)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def read_daily(path, source="ssi"):
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError("Chưa có kho dữ liệu ngày. Chạy history-v3 trước.")
    # immutable=1 on read-only hosts (Vercel) so SQLite never tries to create side files.
    suffix = "?mode=ro&immutable=1" if os.environ.get("VERCEL") else "?mode=ro"
    with sqlite3.connect(path.as_uri() + suffix, uri=True) as db:
        rows = db.execute("SELECT fetched_at,payload FROM daily_summary WHERE source=? ORDER BY trading_date,index_group,symbol",
                          (source,)).fetchall()
    frame = pd.DataFrame([{**json.loads(payload), "fetched_at": fetched, "source": source} for fetched, payload in rows])
    return frame
