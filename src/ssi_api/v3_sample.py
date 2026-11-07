"""Synthetic FastConnect V3 frames in the wire shape read from ``ssi-sdk`` 3.3.2.

DỮ LIỆU GIẢ LẬP: tickers are fictional (V3HOSExx / V3HNXxx). Used by tests and offline demos;
it says nothing about real SSI values, units or update frequency.
"""
from datetime import timedelta

from src.data.store import timestamp
from src.ssi_api.stream_collector import Frame


def v3_members(per_group=11):
    return ([{"symbol": f"V3HOSE{i:02d}", "index_group": "VN30", "marketCode": "HOSE"} for i in range(1, per_group + 1)]
            + [{"symbol": f"V3HNX{i:02d}", "index_group": "HNX30", "marketCode": "HNX"} for i in range(1, per_group + 1)])


def frame(topic, data, received):
    return Frame({"channel": "DATA", "topic": topic, "data": data}, received.isoformat())


def baseline_frames(members, at, *, flag=True, seed=0):
    """One trade, quote and room frame per member, source time one second before receipt."""
    received = timestamp(at)
    source = (received - timedelta(seconds=1)).strftime("%H:%M:%S")
    frames = []
    if flag:
        frames += [frame("market.flag", {"b": board, "t": source, "f": "LO"}, received) for board in ("HOSE", "HNX")]
    for n, member in enumerate(members):
        k = (n * 7 + seed) % 11
        base = 20_000 + 500 * n
        last = base * (1 + (k - 5) / 200)
        volume = 100_000 + 15_000 * k
        avg = (base + last) / 2
        symbol = member["symbol"]
        frames.append(frame(f"trade.{symbol}", {"s": symbol, "t": source, "p": round(last), "q": 100, "si": "B",
                                                 "v": volume, "o": base, "h": max(base, last), "l": min(base, last), "a": avg},
                            received))
        bids = [[round(last) - 50 * i, 1_000 * (i + k)] for i in range(1, 4)]
        asks = [[round(last) + 50 * i, 1_000 * (i + (10 - k))] for i in range(1, 4)]
        frames.append(frame(f"quote.{symbol}", {"s": symbol, "t": source, "bids": bids, "asks": asks}, received))
        buy = 2_000 + 300 * k
        sell = 3_500 - 250 * k
        frames.append(frame(f"room.{symbol}", {"s": symbol, "t": source, "tr": 1_000_000, "cr": 400_000,
                                                "bq": buy, "bv": buy * last, "sq": max(sell, 0), "sv": max(sell, 0) * last},
                            received))
    return frames


def v3_scenario(start="2026-11-04T10:00:00+07:00", per_group=11, flag=True):
    """A baseline, a later quote update and a disconnect, then a fresh baseline after reconnect."""
    members = v3_members(per_group)
    origin = timestamp(start)
    first = baseline_frames(members, origin + timedelta(seconds=1), flag=flag)
    probe = members[0]["symbol"]
    later = origin + timedelta(seconds=30)
    first.append(frame(f"quote.{probe}", {"s": probe, "t": (later - timedelta(seconds=1)).strftime("%H:%M:%S"),
                                          "bids": [[20_000, 9_000], [19_950, 8_000], [19_900, 7_000]],
                                          "asks": [[20_050, 500], [20_100, 400], [20_150, 300]]}, later))
    from src.ssi_api.stream_collector import StreamDisconnected
    first.append(StreamDisconnected())
    second = baseline_frames(members, origin + timedelta(seconds=60), flag=flag, seed=3)
    return members, [first, second]


class SampleFactory:
    """Offline V3 transport over the scripted frames above (source=synthetic, never ssi)."""
    profile = "fastconnect_v3"

    def __new__(cls, members, scripts, clock):
        from src.ssi_api.fake_stream import FakeFactory
        factory = FakeFactory(members, scripts, clock)
        factory.profile = cls.profile
        return factory


def save_v3_sample(database):
    from src.data.ssi_journal import BufferedSink
    from src.data.store import EventStore
    from src.ssi_api.fake_stream import FakeClock
    from src.ssi_api.stream_collector import collect_stream
    members, scripts = v3_scenario()
    clock = FakeClock()
    store = EventStore(database)
    sink = BufferedSink(store)
    try:
        result = collect_stream(SampleFactory(members, scripts, clock), sink, seconds=90, max_messages=1000,
                                idle_seconds=120, clock=clock.monotonic, sleep=clock.sleep, wall_now=clock.wall_now)
        sink.flush()
    finally:
        store.close()
    return result


def main():
    """python -m src.ssi_api.v3_sample : build runtime/v3-synthetic.sqlite and print checkpoints."""
    import json
    import sys
    from src.analytics.sessions import report_frame
    from src.config import PROJECT_ROOT
    from src.ranking.engine import rank_groups
    from src.ssi_api.replay import replay
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    database = PROJECT_ROOT / "runtime" / "v3-synthetic.sqlite"
    for suffix in ("", "-wal", "-shm"):
        path = database.with_name(database.name + suffix)
        if path.exists():
            path.unlink()
    collected = save_v3_sample(database)
    checkpoints = []
    for at, label in (("2026-11-04T10:00:20+07:00", "sau dữ liệu nền"), ("2026-11-04T10:00:45+07:00", "sau mất kết nối"),
                      ("2026-11-04T10:01:05+07:00", "sau dữ liệu nền mới")):
        report = replay(database, collected["run"], as_of=at)
        ranked = rank_groups(report_frame(report), semantics_verified=False)
        top = {g: part.dropna(subset=["rank"]).sort_values("rank").head(3)[["symbol", "total_score"]].round(1).values.tolist()
               for g, part in ranked.groupby("index_group")}
        checkpoints.append({"as_of": at, "label": label, "connection": report["last_recorded_connection_state"],
                            "usable": {g: c["data_usable"] for g, c in report["group_coverage"].items()},
                            "ranked": {g: int(part["rank"].notna().sum()) for g, part in ranked.groupby("index_group")},
                            "top3": top,
                            "warnings": sorted({w for row in report["rows"] for w in row["warnings"]})})
    print(json.dumps({"label": "DỮ LIỆU GIẢ LẬP V3 — mã hư cấu", "database": str(database), "run": collected["run"],
                      "counters": collected["counters"], "checkpoints": checkpoints}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
