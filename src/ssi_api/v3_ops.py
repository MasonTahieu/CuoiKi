"""Operational commands for FastConnect V3: smoke test, timed collection, history, reconciliation.

Every function here that touches the network is reached only through an explicit CLI command.
Reports contain counts, field names, time formats and public market values; never keys,
tokens, OTP or account data.
"""
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
import json
import re
import statistics

from pathlib import Path

from src.analytics.sessions import evaluate_run
from src.config import PROJECT_ROOT
from src.data.daily_store import DailyStore, default_daily_path
from src.data.ssi_journal import BufferedSink, SSIJournal
from src.data.store import EventStore, TZ, now, timestamp
from src.ssi_api.replay import replay
from src.ssi_api.stream_collector import collect_stream
from src.ssi_api.v3_client import EXPECTED_BOARD, V3Client, resolve_members
from src.ssi_api.v3_decoder import source_time
from src.ssi_api.v3_stream import V3Factory

DEFAULT_WINDOWS = ((time(8, 58), time(11, 31)), (time(12, 59), time(14, 46)))
DAILY_DB = default_daily_path()
SUMMARY_AT = time(15, 5)
STREAM_WINDOWS = (("sang", time(8, 55), time(11, 35)), ("chieu", time(12, 55), time(15, 5)))
STREAM_DB = PROJECT_ROOT / "runtime" / "ssi-stream.sqlite"
STREAM_EVIDENCE = PROJECT_ROOT / "evidence" / "v3_sessions" / "stream"


def time_format(value):
    """Shape of the source timestamp, without the value itself."""
    if isinstance(value, bool) or value is None:
        return "missing"
    if isinstance(value, (int, float)):
        return "epoch_ms" if value > 1e11 else "epoch_s"
    text = str(value)
    shape = re.sub(r"\d", "9", text)
    return shape[:32]


def login(settings, otp_mode=None, read_otp=None, notify=print, client=None):
    client = client or V3Client(settings)
    client.login(otp_mode, read_otp, notify)
    return client


def collect(settings, client, *, seconds, database=None, ws_factory=None, idle_seconds=120, max_reconnects=20,
            groups=("VN30",)):
    store = EventStore(database or settings.database)
    sink = BufferedSink(store, batch_size=256)
    factory = V3Factory(client, groups, settings.subscribe_mode, ws_factory)
    try:
        result = collect_stream(factory, sink, seconds=seconds, max_messages=10_000_000,
                                max_reconnects=max_reconnects, idle_seconds=idle_seconds)
        sink.flush()
    finally:
        store.close()
    stream = factory.last_stream
    result["acks"] = dict(stream.acks) if stream else {}
    result["network_called"] = True
    return result


def journal_profile(path, run):
    """Counts and field presence per V3 message type, read back from the journal."""
    types, fields, formats, levels, prices = Counter(), defaultdict(Counter), defaultdict(Counter), Counter(), []
    samples = {}
    with SSIJournal(path) as journal:
        for event in journal.events(run):
            if event["channel"] == "ssiRaw":
                message = event["payload"].get("message", {})
                kind = message.get("message_type")
                types[kind] += 1
                data = message.get("data", {})
                for key in data:
                    fields[kind][key] += 1
                formats[kind][time_format(data.get("t"))] += 1
                if kind == "QUOTE":
                    levels[f"bids={len(data.get('bids') or [])}/asks={len(data.get('asks') or [])}"] += 1
                if kind == "TRADE" and isinstance(data.get("p"), (int, float)):
                    prices.append(data["p"])
                samples.setdefault(kind, message)
    return {"message_types": dict(types), "fields_by_type": {k: dict(v) for k, v in fields.items()},
            "source_time_formats": {k: dict(v) for k, v in formats.items()}, "quote_levels": dict(levels),
            "trade_price_median": statistics.median(prices) if prices else None, "samples": samples}


def last_stream_totals(path, run):
    """Latest stream-side cumulative totals per symbol from decoded records."""
    totals = {}
    with SSIJournal(path) as journal:
        for event in journal.events(run):
            if event["channel"] != "ssiDecoded":
                continue
            payload = event["payload"]["payload"]
            entry = totals.setdefault(payload["symbol"], {})
            for key in ("totalTradingVolume", "totalTradingValue", "foreignBuyValue", "foreignSellValue",
                        "foreignBuyVolume", "foreignSellVolume", "openPrice", "closePrice"):
                if payload.get(key) is not None:
                    entry[key] = payload[key]
    return totals


def reconcile(stream_totals, summaries):
    """Compare stream totals with REST daily totals of the same day. Ratios near 1 support units."""
    rows = []
    by_symbol = {row["symbol"]: row for row in summaries}
    for symbol, stream in sorted(stream_totals.items()):
        rest = by_symbol.get(symbol)
        if not rest:
            continue
        row = {"symbol": symbol, "index_group": rest["index_group"]}
        for key in ("totalTradingVolume", "totalTradingValue", "foreignBuyValue", "foreignSellValue", "openPrice"):
            a, b = stream.get(key), rest.get(key)
            row[f"stream_{key}"], row[f"rest_{key}"] = a, b
            row[f"ratio_{key}"] = (a / b) if isinstance(a, (int, float)) and isinstance(b, (int, float)) and b else None
        rows.append(row)
    summary = {}
    for key in ("totalTradingVolume", "totalTradingValue", "foreignBuyValue", "foreignSellValue", "openPrice"):
        ratios = [r[f"ratio_{key}"] for r in rows if r[f"ratio_{key}"] is not None]
        summary[key] = {"symbols": len(ratios), "median_ratio": statistics.median(ratios) if ratios else None,
                        "min_ratio": min(ratios) if ratios else None, "max_ratio": max(ratios) if ratios else None}
    return {"rows": rows, "summary": summary,
            "note": "Tỷ lệ stream/REST gần 1 ủng hộ cách hiểu đơn vị; lệch có hệ thống cần đối chiếu trước khi bật SSI_SEMANTICS_VERIFIED."}


def fetch_summaries(client, day, groups=("VN30",), members=None):
    """Per-member daily rows for one day (``index=`` would return the index itself)."""
    members = members or resolve_members(client, groups)[0]
    return client.member_summaries(members, day, day)


def history(settings, client, *, sessions=10, database=DAILY_DB, today=None, groups=("VN30",)):
    """Fetch about ``sessions`` trading days of daily summaries (calendar window ×1.6 + 7)."""
    today = today or datetime.now(TZ).date()
    start = today - timedelta(days=int(sessions * 1.6) + 7)
    members, warning = resolve_members(client, groups, database)
    rows = client.member_summaries(members, start, today)
    index_rows = [row for group in groups for row in client.summaries(group, start, today)]
    days = sorted({row["tradingDate"] for row in rows})
    keep = set(days[-sessions:])
    rows = [row for row in rows if row["tradingDate"] in keep]
    index_rows = [{**row, "index_group": "INDEX"} for row in index_rows if row["tradingDate"] in keep]
    with DailyStore(database) as store:
        store.upsert("ssi", rows + index_rows, now())
    per_day = {day: sum(r["tradingDate"] == day for r in rows) for day in sorted(keep)}
    return {"source": "ssi", "groups": list(groups), "members": len(members), "sessions": len(keep),
            "trading_dates": sorted(keep), "rows": len(rows), "index_rows": len(index_rows),
            "rows_per_day": per_day, "database": str(database), "member_warning": warning, "network_called": True}


def smoke(settings, client, *, seconds=30, out_root=None, ws_factory=None, today=None, database=None):
    """Login is done by the caller. Read universe + today's summary, stream briefly, write evidence."""
    out_root = out_root or PROJECT_ROOT / "evidence" / "v3_smoke"
    stamp = datetime.now(TZ).strftime("%Y%m%d-%H%M%S")
    folder = out_root / stamp
    folder.mkdir(parents=True, exist_ok=True)
    database = database or PROJECT_ROOT / "runtime" / "ssi-smoke.sqlite"
    report = {"schema_version": "ssi-v3-smoke-1", "started_at": now(), "login_mode": client.login_mode, "steps": {}}
    members, warning = resolve_members(client)
    report["steps"]["universe"] = {"VN30": sum(m["index_group"] == "VN30" for m in members)}
    if warning:
        report["steps"]["universe"]["warning"] = warning
    today = today or datetime.now(TZ).date()
    summaries = [row for group in ("VN30",) for row in client.summaries(group, today, today)]
    report["steps"]["summary_today"] = {"index_rows": len(summaries),
        "present_fields": sorted({f for row in summaries for f in row["present_fields"].split(";") if f})}
    collected = collect(settings, client, seconds=seconds, database=database, ws_factory=ws_factory,
                        idle_seconds=max(30, seconds), max_reconnects=1)
    report["steps"]["stream"] = {k: collected[k] for k in ("stop_reason", "counters", "acks")}
    profile = journal_profile(database, collected["run"])
    report["steps"]["stream_profile"] = profile
    quality = replay(database, collected["run"])
    report["steps"]["quality"] = {"group_coverage": {g: {k: v for k, v in c.items() if k != "fields"}
                                  for g, c in quality["group_coverage"].items()},
                                  "reasons": dict(Counter(r for row in quality["rows"] for r in row["reasons"])),
                                  "warnings": dict(Counter(w for row in quality["rows"] for w in row["warnings"]))}
    refreshed = fetch_summaries(client, today, members=members)
    report["steps"]["reconciliation"] = reconcile(last_stream_totals(database, collected["run"]), refreshed)["summary"]
    report["finished_at"] = now()
    report["run"] = collected["run"]
    report["database"] = str(database)
    (folder / "smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (folder / "SMOKE.md").write_text(smoke_markdown(report), encoding="utf-8")
    report["output"] = str(folder)
    return report


def smoke_markdown(report):
    s = report["steps"]
    stream = s["stream"]
    lines = ["# Smoke test FastConnect V3", "",
             f"Bắt đầu {report['started_at']} · kết thúc {report['finished_at']} · đăng nhập `{report['login_mode']}`.", "",
             "| Bước | Kết quả |", "|---|---|",
             f"| Thành phần nhóm | VN30 {s['universe']['VN30']} mã |",
             f"| securitiesSummary chỉ số hôm nay | {s['summary_today']['index_rows']} dòng |",
             f"| Stream | dừng vì `{stream['stop_reason']}` · nhận {stream['counters']['received']} · ghép {stream['counters']['merged']} · lỗi giải mã {stream['counters']['decode_errors']} |",
             f"| Ack đăng ký | {stream['acks']} |",
             f"| Loại thông điệp | {s['stream_profile']['message_types']} |",
             f"| Mẫu thời gian nguồn | {s['stream_profile']['source_time_formats']} |",
             f"| Số mức sổ lệnh | {s['stream_profile']['quote_levels']} |",
             f"| Trung vị giá khớp | {s['stream_profile']['trade_price_median']} |", "",
             "## Chất lượng sau phát lại", "", "```json", json.dumps(s["quality"], ensure_ascii=False, indent=2), "```", "",
             "## Đối chiếu stream với REST cùng ngày", "", "```json",
             json.dumps(s["reconciliation"], ensure_ascii=False, indent=2), "```", "",
             "Không bật `SSI_SEMANTICS_VERIFIED=true` chỉ dựa trên một lần smoke test.", ""]
    return "\n".join(lines)


def _spread(values):
    if not values:
        return None
    ordered = sorted(values)
    return {"count": len(ordered), "p50": round(statistics.median(ordered), 2),
            "p99": round(ordered[min(len(ordered) - 1, int(.99 * len(ordered)))], 2),
            "min": round(ordered[0], 2), "max": round(ordered[-1], 2)}


def stream_stats(path, run):
    """Lag, cadence, session flags and connection changes of a run. Counts and times, no prices."""
    lags, gaps, previous, flags, connections = defaultdict(list), defaultdict(list), {}, [], []
    with SSIJournal(path) as journal:
        for event in journal.events(run):
            if event["channel"] == "connection":
                state = event["payload"].get("state")
                if state not in {"duplicate", "rejected"}:
                    connections.append({"at": event["received_at"], "state": state})
                continue
            if event["channel"] != "ssiRaw":
                continue
            message = event["payload"].get("message", {})
            kind, data = message.get("message_type"), message.get("data") or {}
            received = timestamp(event["received_at"])
            source, _ = source_time(data.get("t"), received)
            if kind == "MARKET_FLAG":
                if data.get("b") == EXPECTED_BOARD["VN30"]:
                    flags.append({"at": event["received_at"], "flag": data.get("f")})
                continue
            if source is not None:
                lags[kind].append((received - source).total_seconds())
            key = (kind, data.get("s"))
            if key in previous:
                gaps[kind].append((received - previous[key]).total_seconds())
            previous[key] = received
    return {"lag_seconds": {k: _spread(v) for k, v in lags.items()}, "gap_seconds": {k: _spread(v) for k, v in gaps.items()},
            "session_flags": flags, "connections": connections}


def stream_window_for(at):
    """The window still open or still ahead at ``at``; None once the afternoon one is over."""
    for label, start, end in STREAM_WINDOWS:
        if at.time() < end:
            return label, datetime.combine(at.date(), start, tzinfo=TZ), datetime.combine(at.date(), end, tzinfo=TZ)
    return None


def stream_window(settings, login, *, trial_seconds=None, clock=None, sleep=None, ws_factory=None, database=None, out_root=None):
    """Wait for today's window, collect until it ends, write a summary. Exits quietly if nothing is left to do."""
    import time as _time
    clock = clock or (lambda: datetime.now(TZ))
    sleep = sleep or _time.sleep
    database, out_root = Path(database or STREAM_DB), Path(out_root or STREAM_EVIDENCE)
    current = clock()
    if trial_seconds:
        label, seconds = "thu", int(trial_seconds)
    else:
        window = stream_window_for(current) if current.weekday() < 5 else None
        if window is None:
            return {"skipped": "hết khung giờ hôm nay"}
        label, start, end = window
        if (out_root / f"stream-{current.date().isoformat()}-{label}.json").exists():
            return {"skipped": f"đã có bản tóm tắt khung {label}"}
        while clock() < start:
            sleep(min(30, (start - clock()).total_seconds()))
        seconds = int((end - clock()).total_seconds())
    output = out_root / f"stream-{current.date().isoformat()}-{label}.json"
    client = login()
    reconciliation = None
    try:
        collected = collect(settings, client, seconds=seconds, database=database, ws_factory=ws_factory)
        if label == "chieu":
            try:
                reconciliation = reconcile(last_stream_totals(database, collected["run"]),
                                           fetch_summaries(client, current.date()))["summary"]
            except Exception as error:  # the capture matters more than this comparison
                reconciliation = {"error": type(error).__name__}
    finally:
        client.close()
    report = {"schema_version": "ssi-v3-stream-window-1", "window": label, "trading_date": current.date().isoformat(),
              "run": collected["run"], "stop_reason": collected["stop_reason"], "counters": collected["counters"],
              "acks": collected["acks"], "reconciliation": reconciliation, "finished_at": now()}
    try:
        report.update(stream_stats(database, collected["run"]))
        evaluation = evaluate_run(database, collected["run"], semantics_verified=settings.semantics_verified)
        report["evaluation"] = {k: evaluation[k] for k in ("first_received_at", "last_received_at", "checkpoints", "update_intervals", "exploratory_ranking")}
    except Exception as error:  # keep the counters above even if the analysis of a run fails
        report["analysis_error"] = f"{type(error).__name__}: {error}"
    out_root.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return {"output": str(output), "window": label, "run": collected["run"], "stop_reason": collected["stop_reason"],
            "counters": collected["counters"], "acks": collected["acks"], "analysis_error": report.get("analysis_error")}


def windows_today(windows=DEFAULT_WINDOWS, at=None):
    at = timestamp(at or now())
    return [(datetime.combine(at.date(), a, tzinfo=TZ), datetime.combine(at.date(), b, tzinfo=TZ)) for a, b in windows]


def session(settings, client, *, windows=DEFAULT_WINDOWS, sleep=None, clock=None, ws_factory=None, database=None):
    """Collect each window of today in its own run, then reconcile with REST at the end."""
    import time as _time
    sleep = sleep or _time.sleep
    clock = clock or (lambda: datetime.now(TZ))
    database = database or settings.database
    results = []
    for start, end in windows_today(windows, clock().isoformat()):
        current = clock()
        if current >= end:
            results.append({"window": [start.isoformat(), end.isoformat()], "skipped": "đã qua khung giờ"})
            continue
        if current < start:
            sleep((start - current).total_seconds())
        seconds = max(1, int((end - clock()).total_seconds()))
        collected = collect(settings, client, seconds=seconds, database=database, ws_factory=ws_factory)
        results.append({"window": [start.isoformat(), end.isoformat()], "run": collected["run"],
                        "stop_reason": collected["stop_reason"], "counters": collected["counters"], "acks": collected["acks"]})
    day = clock().date()
    final = datetime.combine(day, SUMMARY_AT, tzinfo=TZ)
    if clock() < final:
        sleep((final - clock()).total_seconds())  # wait for ATC and put-through totals to settle
    summaries = fetch_summaries(client, day)
    with DailyStore(DAILY_DB) as store:
        store.upsert("ssi", summaries, now())
    reconciliations = {item["run"]: reconcile(last_stream_totals(database, item["run"]), summaries)["summary"]
                       for item in results if item.get("run")}
    report = {"schema_version": "ssi-v3-session-1", "trading_date": day.isoformat(), "windows": results,
              "summary_rows": len(summaries), "reconciliation": reconciliations, "finished_at": now()}
    folder = PROJECT_ROOT / "evidence" / "v3_sessions"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"session-{day.isoformat()}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["output"] = str(folder / f"session-{day.isoformat()}.json")
    return report
