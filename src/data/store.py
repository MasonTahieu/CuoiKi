"""Append-only market event journal, separated by source and collection run."""
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
CHANNELS = {"stockInfo", "marketSession", "marketInfo", "marketVolume", "universe", "connection", "ssiRaw", "ssiDecoded", "ssiMerged"}


def timestamp(value):
    dt = datetime.fromisoformat(value) if isinstance(value, str) else value
    if dt.tzinfo is None:
        raise ValueError("Thời gian phải kèm múi giờ.")
    return dt.astimezone(TZ)


def now():
    return datetime.now(TZ).isoformat()


def redact(value):
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items() if not any(
            s in k.lower() for s in ("token", "password", "authorization", "username", "account", "device", "secret", "consumerid", "api_key", "apikey"))}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


class EventStore:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY, source TEXT NOT NULL, run TEXT NOT NULL,
            received_at TEXT NOT NULL, channel TEXT NOT NULL, payload TEXT NOT NULL,
            fingerprint TEXT NOT NULL UNIQUE)""")
        self.db.execute("CREATE INDEX IF NOT EXISTS event_run ON events(run, id)")
        self.db.commit()

    def append(self, source, run, received_at, channel, payload):
        self.append_many([dict(source=source,run=run,received_at=received_at,channel=channel,payload=payload)])

    @staticmethod
    def _prepare(source, run, received_at, channel, payload):
        if source not in {"synthetic", "neo", "ssi"} or channel not in CHANNELS:
            raise ValueError("Nguồn/kênh dữ liệu không được hỗ trợ.")
        stamp = timestamp(received_at).isoformat()
        content = json.dumps(redact(payload), ensure_ascii=False, sort_keys=True, allow_nan=False)
        digest = hashlib.sha256(json.dumps([source, run, stamp, channel, content]).encode()).hexdigest()
        return source,run,stamp,channel,content,digest

    def append_many(self, events):
        """One atomic batch; a failed event rolls back all insertions in that batch."""
        before=self.db.total_changes
        with self.db:
            for event in events:
                self.db.execute("INSERT OR IGNORE INTO events(source,run,received_at,channel,payload,fingerprint) VALUES(?,?,?,?,?,?)",
                                self._prepare(**event))
        return self.db.total_changes-before

    def close(self):
        self.db.close()


def read_events(path, run=None):
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError("Chưa có kho dữ liệu. Chạy demo-pipeline hoặc collect trước.")
    try:
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
            if run is None:
                found = db.execute("SELECT run FROM events ORDER BY id DESC LIMIT 1").fetchone()
                if not found:
                    raise ValueError("Kho dữ liệu chưa có sự kiện.")
                run = found[0]
            rows = db.execute("SELECT source,run,received_at,channel,payload FROM events WHERE run=? ORDER BY id", (run,)).fetchall()
    except sqlite3.Error:
        raise ValueError("Không đọc được kho sự kiện SQLite; kiểm tra đúng tệp và cấu trúc dữ liệu.") from None
    return [dict(source=s, run=r, received_at=t, channel=c, payload=json.loads(p)) for s,r,t,c,p in rows]
