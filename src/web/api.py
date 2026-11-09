"""JSON payloads for the web UI. Pure functions over the existing pipeline; no HTTP here.

Sources:
  demo-board    synthetic 24-ticker scoreboard (legacy stockInfo events, state_at)
  demo-journal  synthetic SSI journals (FCData v2 samples and the V3 sample), replayed
  store         the configured SSI journal (replay/live) or a legacy event store
"""
from copy import deepcopy
from datetime import timedelta
from functools import lru_cache
import csv
import io
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from src.config import load_settings
from src.data.normalize import recorded_update_mode, state_at
from src.data.ssi_journal import SSIJournal
from src.data.store import now, read_events, timestamp
from src.data.synthetic import demo_events, demo_groups
from src.providers import load_provider_settings
from src.ranking.engine import FACTOR_NAMES, rank_groups
from src.ranking import daily as daily_rank

from src.data.daily_store import default_daily_path

DAILY_DB = default_daily_path()
DAILY_RUN = "ssi-daily"

GROUPS = ("VN30",)
WEIGHTS = {"balanced": dict.fromkeys(FACTOR_NAMES, 0.25),
           "momentum": {"momentum": .4, "liquidity": .2, "foreign": .2, "imbalance": .2}}
WEIGHT_LABELS = {"balanced": "Cân bằng 25/25/25/25", "momentum": "Ưu tiên động lượng 40/20/20/20"}
FACTOR_LABELS = {"momentum": "Động lượng", "liquidity": "Thanh khoản", "foreign": "Dòng tiền ngoại", "imbalance": "Cung–cầu"}
CONNECTION = {
    "unknown": ("Chưa rõ kết nối", "muted"), "connecting": ("Đang kết nối", "warn"),
    "awaiting_bootstrap": ("Chờ dữ liệu nền", "warn"), "connected": ("Đã kết nối", "ok"),
    "disconnected": ("Mất kết nối", "bad"), "auth_failed": ("Xác thực thất bại", "bad"),
    "adapter_error": ("Lỗi bộ kết nối", "bad"), "stopped": ("Đã dừng thu thập", "muted"),
    "recorded": ("Dữ liệu đã ghi", "muted"), "demo": ("Bảng điểm giả lập", "muted"),
}
# One short status per stock; the first matching reason wins (most actionable first).
REASON_STATUS = [
    ("CONNECTION_NOT_ACTIVE", "disconnected", "Không có kết nối"),
    ("NO_BASELINE", "waiting", "Chờ dữ liệu nền"),
    ("STATUS_NOT_NORMAL", "halt", "Tạm ngừng GD"),
    ("SESSION_NOT_LO", "session", "Ngoài phiên LO"),
    ("STALE_FIELDS", "stale", "Dữ liệu cũ"),
    ("MISSING_FIELDS", "missing", "Thiếu dữ liệu"),
    ("INVALID_VALUES", "invalid", "Giá trị lỗi"),
    ("FIELD_TIME_MISSING", "missing", "Thiếu giờ nguồn"),
    ("EXCESS_RECORDED_LAG", "stale", "Trễ dữ liệu"),
    ("COUNTER_DECREASE", "invalid", "Lũy kế giảm"),
]
REASON_TEXT = {
    "CONNECTION_NOT_ACTIVE": "Kết nối không hoạt động tại mốc chọn", "NO_BASELINE": "Chưa có dữ liệu nền của lần kết nối hiện tại",
    "MISSING_FIELDS": "Thiếu trường bắt buộc", "INVALID_VALUES": "Giá trị không hợp lệ", "STALE_FIELDS": "Trường quá ngưỡng tuổi",
    "FIELD_TIME_MISSING": "Thiếu dấu thời gian nguồn/nhận", "EXCESS_RECORDED_LAG": "Chênh thời gian nguồn–nhận vượt ngưỡng",
    "SESSION_NOT_LO": "Ngoài phiên khớp lệnh liên tục LO", "STATUS_NOT_NORMAL": "Mã không ở trạng thái giao dịch bình thường",
    "COUNTER_DECREASE": "Số liệu lũy kế giảm bất thường",
}
LEGACY_STATUS = [
    ("chưa có snapshot", "waiting", "Chờ dữ liệu nền"), ("trạng thái cổ phiếu", "halt", "Tạm ngừng GD"),
    ("ngoài phiên", "session", "Ngoài phiên LO"), ("cũ", "stale", "Dữ liệu cũ"), ("thiếu", "missing", "Thiếu dữ liệu"),
    ("ATO/ATC", "session", "Giá phiên định kỳ"), ("cộng dồn", "invalid", "Lũy kế giảm"),
]
WARNING_TEXT = {
    "FOREIGN_VALUE_ESTIMATED": "Giá trị ngoại ước tính", "SOURCE_CLOCK_AHEAD_OF_RECEIVE": "Đồng hồ nguồn đi trước giờ nhận",
    "SESSION_FROM_SCHEDULE": "Phiên suy từ lịch giao dịch", "SYMBOL_STATUS_NOT_PROVIDED": "Nguồn không gửi trạng thái từng mã",
    "TOTAL_VALUE_DERIVED": "Giá trị khớp = giá bình quân × khối lượng",
}
CLUSTERS = {"trade": ("closePrice", "totalTradingValue"),
            "book": tuple(f"{s}{k}{i}" for s in ("bid", "ask") for k in ("Price", "Vol") for i in (1, 2, 3)),
            "foreign": ("foreignBuyValue", "foreignSellValue")}


class ApiError(ValueError):
    """Message is safe to show in the UI."""


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


# -- sources ----------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _demo_journals():
    """Sample journals are built once per process in a temporary folder (synthetic only)."""
    from src.ssi_api.collect_sample import scenario
    from src.ssi_api.replay_sample import save_sample, stale_scenario
    from src.ssi_api.v3_sample import save_v3_sample
    folder = TemporaryDirectory(prefix="screener-web-demo-")
    path = Path(folder.name) / "demo.sqlite"
    v3 = save_v3_sample(path)
    primary = save_sample(path, *scenario())
    stale = save_sample(path, *stale_scenario(), seconds=65, max_messages=100)
    labels = {v3["run"]: "V3 · mất kết nối, dựng lại",
              primary["run"]: "FCData v2 · mất kết nối và phục hồi",
              stale["run"]: "FCData v2 · khối ngoại cũ"}
    return folder, path, labels


def context():
    settings = load_settings()
    provider = load_provider_settings(settings.provider)
    sources = []
    if settings.mode == "demo":
        sources = [{"id": "demo-board", "label": "Minh họa · Bảng điểm giả lập"},
                   {"id": "demo-journal", "label": "Minh họa · Nhật ký SSI mẫu"}]
    elif settings.provider == "ssi" and Path(provider.database).is_file():
        sources = [{"id": "store", "label": "Kho SSI cục bộ"}]
    elif Path(getattr(provider, "database", "")).is_file():
        sources = [{"id": "store", "label": "Kho cục bộ"}]
    if Path(DAILY_DB).is_file():  # real data first: the page opens on the first source
        sources.insert(0, {"id": "daily", "label": "Cuối ngày · SSI thật"})
    return {"mode": settings.mode, "provider": settings.provider, "profile": getattr(provider, "profile", None),
            "semantics_verified": bool(provider.semantics_verified), "sources": sources,
            "weights": [{"id": k, "label": v} for k, v in WEIGHT_LABELS.items()],
            "foreign": [{"id": "value", "label": "Theo giá trị"}, {"id": "volume", "label": "Theo khối lượng"}],
            "refresh": [0, 10, 30] if settings.mode == "live" else [],
            "compare": [{"id": k, "label": v} for k, v in COMPARE.items()],
            "now": now()}


def _store_kind(provider):
    path = Path(provider.database)
    if not path.is_file():
        raise ApiError("Chưa có kho dữ liệu. Chạy collector hoặc dùng APP_MODE=demo.")
    with SSIJournal(path) as journal:
        runs = journal.runs()
    return ("journal", path, runs) if runs else ("events", path, [])


def runs(source):
    settings = load_settings()
    if source == "daily":
        _daily_frame()
        return [{"id": DAILY_RUN, "label": "Dữ liệu ngày SSI (REST)", "source": "ssi"}]
    if source == "demo-board":
        return [{"id": "synthetic-vn30-v1", "label": "Bảng điểm giả lập", "source": "synthetic"}]
    if source == "demo-journal":
        _, path, labels = _demo_journals()
        return [{"id": run, "label": label, "source": "synthetic"} for run, label in labels.items()]
    if source == "store":
        provider = load_provider_settings(settings.provider)
        kind, path, found = _store_kind(provider)
        if kind == "journal":
            if settings.mode == "live":
                found = [r for r in found if r["source"] == "ssi"]
            return [{"id": r["run"], "label": f"{timestamp(r['last_received_at']):%d/%m %H:%M:%S} · {r['source']} · …{r['run'][-6:]}",
                     "source": r["source"]} for r in found]
        events = read_events(path)
        return [{"id": events[0]["run"], "label": f"Lần thu thập …{events[0]['run'][-6:]}", "source": events[0]["source"]}]
    raise ApiError("Nguồn dữ liệu không hợp lệ.")


def _journal_path(source):
    if source == "demo-journal":
        return _demo_journals()[1]
    settings = load_settings()
    return Path(load_provider_settings(settings.provider).database)


def _legacy_events(source):
    if source == "demo-board":
        settings = load_settings()
        return demo_groups() if settings.provider == "ssi" else demo_events()
    settings = load_settings()
    return read_events(load_provider_settings(settings.provider).database)


def _is_journal(source):
    if source == "demo-journal":
        return True
    if source == "demo-board":
        return False
    settings = load_settings()
    return _store_kind(load_provider_settings(settings.provider))[0] == "journal"


def _daily_frame():
    from src.data.daily_store import read_daily
    if not Path(DAILY_DB).is_file():
        raise ApiError("Chưa có dữ liệu ngày. Chạy .\\SSI_V3.ps1 -Lenh lichsu trước.")
    frame = read_daily(DAILY_DB)
    return frame[frame["index_group"].isin(GROUPS)] if not frame.empty else frame


def _day_id(day):
    return f"{day}T15:00:00+07:00"


def timeline(source, run):
    if source == "daily":
        days = sorted(_daily_frame()["tradingDate"].unique())
        return [{"id": _day_id(d), "at": _day_id(d), "label": f"Phiên {d[8:10]}/{d[5:7]}/{d[:4]}", "kind": "day",
                 "severity": "info"} for d in days]
    if _is_journal(source):
        labels = {"connection": None, "ssiDecoded": "Dữ liệu cổ phiếu", "universe": "Danh sách mã"}
        with SSIJournal(_journal_path(source)) as journal:
            points = journal.timeline(run)
        out = []
        for p in points:
            label = labels[p["channel"]] or CONNECTION.get(p["state"], ("Trạng thái", "muted"))[0]
            out.append({"id": str(p["event_id"]), "at": p["received_at"], "label": label,
                        "kind": "data" if p["channel"] == "ssiDecoded" else p["channel"],
                        "severity": CONNECTION.get(p["state"], (None, "muted"))[1] if p["channel"] == "connection" else "info"})
        return out
    events = _legacy_events(source)
    moments = sorted({e["received_at"] for e in events if e["channel"] == "stockInfo"}, key=timestamp)
    return [{"id": m, "at": m, "label": "Dữ liệu cổ phiếu", "kind": "data", "severity": "info"} for m in moments]


# -- snapshot ----------------------------------------------------------------------------------

def _status(reasons_codes, quality_reason):
    for code, kind, label in REASON_STATUS:
        if code in reasons_codes:
            return kind, label
    text = quality_reason or ""
    if "chỉ có" in text and "hợp lệ" in text:
        return "cohort", "Nhóm chưa đủ mã"
    if "chưa xác minh" in text:
        return "unverified", "Chưa xác minh nguồn"
    for needle, kind, label in LEGACY_STATUS:
        if needle in text:
            return kind, label
    return ("invalid", "Không tính được") if text else ("ranked", "Đã xếp hạng")


def _age(row, fields):
    ages = row.get("source_age_seconds", {})
    values = [ages[f] for f in fields if f in ages]
    return max(values) if len(values) == len(fields) else None


def _resolve_journal(source, run, point, mode):
    from src.ssi_api.replay import replay
    path = _journal_path(source)
    if mode == "live" and source == "store" and point in (None, "", "latest"):
        return replay(path, run, as_of=now())
    if point in (None, "", "latest"):
        return replay(path, run)
    try:
        event_id = int(point)
    except ValueError:
        raise ApiError("Mốc phát lại không hợp lệ.") from None
    return replay(path, run, through_event_id=event_id)


def _journal_frame(report):
    import pandas as pd
    rows = []
    for row in report["rows"]:
        rows.append({**row["payload"], "symbol": row["symbol"], "marketCode": row["marketCode"],
                     "index_group": row["index_group"], "source": report["source"], "run": report["run"],
                     "as_of": report["as_of"], "session": row.get("trading_session"),
                     "quality_reason": ";".join(row["reasons"])})
    return pd.DataFrame(rows)


# Measured 09/11/2026: evidence/v3_history/KHOI_NGOAI_THOA_THUAN.md
FOREIGN_SCOPE_NOTE = {
    "label": "Khối ngoại gồm thỏa thuận",
    "detail": "Số khối ngoại của SSI gồm cả giao dịch thỏa thuận, còn giá trị khớp thì không. Một lô thỏa thuận một phía "
              "có thể đẩy điểm khối ngoại của mã đó, và dữ liệu ngày không tách riêng được phần này."}
COMPARE = {"prev": "mốc dữ liệu liền trước", "30": "30 giây trước", "60": "1 phút trước",
           "300": "5 phút trước", "900": "15 phút trước"}


def _compare_point(source, run, current_id, as_of, compare, moments=None):
    """The moment to rank again for change arrows: strictly earlier in time, never a guess."""
    current_at = timestamp(as_of)
    if moments is not None:  # legacy scoreboard: moment ids are ISO times
        earlier = [m for m in moments if timestamp(m) < current_at]
        if compare != "prev":
            limit = current_at - timedelta(seconds=int(compare))
            earlier = [m for m in earlier if timestamp(m) <= limit]
        return earlier[-1] if earlier else None
    target = as_of if compare == "prev" else (current_at - timedelta(seconds=int(compare))).isoformat()
    op = "<" if compare == "prev" else "<="
    with SSIJournal(_journal_path(source)) as journal:
        found = journal.db.execute(
            f"SELECT id FROM events WHERE run=? AND channel='ssiDecoded' AND id<=? AND received_at{op}? ORDER BY id DESC LIMIT 1",
            (run, current_id, timestamp(target).isoformat())).fetchone()
    return str(found[0]) if found else None


def _attach_changes(data, previous):
    for name, group in data["groups"].items():
        before = {r["symbol"]: r for r in previous["groups"].get(name, {}).get("rows", [])}
        for row in group["rows"]:
            old = before.get(row["symbol"])
            row["prev_rank"] = old["rank"] if old else None
            row["prev_total"] = old["total"] if old else None
            both = row["rank"] is not None and row["prev_rank"] is not None
            row["rank_change"] = (row["prev_rank"] - row["rank"]) if both else None
            row["total_change"] = (row["total"] - row["prev_total"]) if both else None
            row["new_in_rank"] = row["rank"] is not None and row["prev_rank"] is None


def _daily_snapshot(point, weights, foreign, compare):
    frame = _daily_frame()
    moments = [p["id"] for p in timeline("daily", DAILY_RUN)]
    if not moments:
        raise ApiError("Kho dữ liệu ngày chưa có phiên nào.")
    as_of = point if point in moments else moments[-1]
    day = as_of[:10]
    weight_map = {**dict.fromkeys(FACTOR_NAMES, 0.0), **daily_rank.WEIGHTS[weights]}
    groups = {}
    for group in GROUPS:
        part = frame[(frame["index_group"] == group) & (frame["tradingDate"] == day)]
        ranked = daily_rank.rank_daily(part.to_dict("records"), weights, foreign)
        rows = []
        for rec in (ranked.to_dict("records") if not ranked.empty else []):
            ok = _num(rec.get("rank")) is not None
            scores = {f: (_num(rec.get(f"score_{f}")) if f != "imbalance" else None) for f in FACTOR_NAMES}
            reason = rec.get("quality_reason") or ""
            kind = "cohort" if "hợp lệ" in reason else "missing"
            rows.append({
                "symbol": rec["symbol"], "rank": int(rec["rank"]) if ok else None, "total": _num(rec.get("total_score")),
                "scores": scores,
                "contributions": {f: (scores[f] * weight_map[f] if scores[f] is not None else None) for f in FACTOR_NAMES},
                "raw": {"momentum": _num(rec.get("momentum")), "turnover": _num(rec.get("turnover")), "spread_bps": None,
                        "depth_vnd": None, "foreign_ratio": _num(rec.get("foreign_ratio")), "imbalance": None,
                        "closePrice": _num(rec.get("closePrice")), "openPrice": _num(rec.get("openPrice")),
                        "totalTradingVolume": _num(rec.get("totalTradingVolume")),
                        "change_pct": _num(rec.get("priceChangePercent")),
                        "foreign_net_value": _net(rec.get("foreignBuyValue"), rec.get("foreignSellValue"))},
                "status": {"kind": "ranked" if ok else kind, "label": "Đã xếp hạng" if ok else
                           ("Nhóm chưa đủ mã" if kind == "cohort" else "Thiếu dữ liệu"), "details": [] if ok else [reason]},
                "warnings": [], "session": "Cuối ngày", "ages": {}, "explanation": None,
            })
        rows.sort(key=lambda r: (r["rank"] is None, r["rank"] or 0, r["symbol"]))
        first = ranked.iloc[0] if len(ranked) else None
        groups[group] = {"members": len(rows), "ranked": sum(r["rank"] is not None for r in rows),
                         "cohort_size": int(first["cohort_size"]) if first is not None else 0,
                         "config_id": first["config_id"] if first is not None else None,
                         "cohort_id": first["cohort_id"] if first is not None else None,
                         "method": daily_rank.METHOD, "usable": None, "rows": rows}
    fetched = frame["fetched_at"].max() if "fetched_at" in frame and len(frame) else None
    result = {
        "source": "ssi", "source_kind": "daily", "run": DAILY_RUN, "as_of": as_of, "last_recorded": fetched,
        "mode": load_settings().mode, "synthetic": False, "profile": "fastconnect_v3",
        # Daily scores are not locked: value units were checked (average price x volume). What the
        # foreign fields measure is stated by scope_note, whatever SSI_SEMANTICS_VERIFIED says.
        "verified": True, "method_kind": "daily",
        "scope_note": FOREIGN_SCOPE_NOTE,
        "connection": {"state": "daily", "label": "Dữ liệu ngày SSI", "severity": "muted", "epoch": None},
        "freshness_seconds": None, "gaps": [], "policy": {"max_age_seconds": 60},
        "weights": {"id": weights, "label": daily_rank.WEIGHT_LABELS[weights], "values": weight_map},
        "foreign": foreign, "groups": groups, "compare": None,
        "pulse": _pulse(groups.get("VN30", {}).get("rows", []), _index_row(day), "phiên trước"),
    }
    if compare:
        target = _compare_point("daily", DAILY_RUN, None, as_of, compare, moments=moments)
        result["compare"] = {"mode": compare, "label": "phiên liền trước" if compare == "prev" else COMPARE[compare],
                             "point": target, "as_of": None}
        if target:
            previous = _daily_snapshot(target, weights, foreign, None)
            result["compare"]["as_of"] = previous["as_of"]
            _attach_changes(result, previous)
    return result


def _net(buy, sell):
    buy, sell = _num(buy), _num(sell)
    return None if buy is None or sell is None else buy - sell


def _index_row(day):
    """VN30 index summary of one trading day (kept as context, not ranked)."""
    from src.data.daily_store import read_daily
    frame = read_daily(DAILY_DB)
    if frame.empty:
        return None
    part = frame[(frame["index_group"] == "INDEX") & (frame["symbol"] == "VN30") & (frame["tradingDate"] == day)]
    if part.empty:
        return None
    rec = part.iloc[-1].to_dict()
    return {"close": _num(rec.get("closePrice")), "change": _num(rec.get("priceChange")),
            "change_pct": _num(rec.get("priceChangePercent")), "value": _num(rec.get("totalTradingValue"))}


def _pulse(rows, index, basis):
    """Basket context at the moment: breadth, matched value and foreign net, from the members' raw data.

    Breadth uses the change against the reference price when the source has it (daily), otherwise
    the change since the open (intraday), and says which.
    """
    changes = []
    for r in rows:
        raw = r.get("raw", {})
        value = raw.get("change_pct") if raw.get("change_pct") is not None else raw.get("momentum")
        if value is not None:
            changes.append(value)
    turnover = [r["raw"]["turnover"] for r in rows if r.get("raw", {}).get("turnover") is not None]
    nets = [r["raw"]["foreign_net_value"] for r in rows if r.get("raw", {}).get("foreign_net_value") is not None]
    eps = 1e-9
    return {"members": len(rows), "priced": len(changes), "basis": basis,
            "advancers": sum(c > eps for c in changes), "decliners": sum(c < -eps for c in changes),
            "unchanged": sum(abs(c) <= eps for c in changes),
            "total_value": sum(turnover) if turnover else None,
            "foreign_net": sum(nets) if nets else None, "foreign_reported": len(nets),
            "index": index}


def _require_daily(source, what):
    if source != "daily":
        raise ApiError(f"{what} chỉ có ở nguồn Cuối ngày · SSI thật (cần dữ liệu nhiều phiên).")


def heatmap(source, weights="balanced", foreign="value"):
    """Rank of every VN30 member in every recorded session, for the rank-history heatmap."""
    _require_daily(source, "Lịch sử hạng")
    if weights not in daily_rank.WEIGHTS or foreign not in ("value", "volume"):
        raise ApiError("Cấu hình trọng số hoặc khối ngoại không hợp lệ.")
    frame = _daily_frame()
    days = sorted(frame["tradingDate"].unique()) if not frame.empty else []
    ranks, reasons = {}, {}
    for i, day in enumerate(days):
        part = frame[(frame["index_group"] == "VN30") & (frame["tradingDate"] == day)]
        ranked = daily_rank.rank_daily(part.to_dict("records"), weights, foreign)
        for rec in ranked.to_dict("records"):
            ranks.setdefault(rec["symbol"], [None] * len(days))[i] = int(rec["rank"]) if _num(rec.get("rank")) is not None else None
            if _num(rec.get("rank")) is None:
                reasons.setdefault(rec["symbol"], {})[i] = rec.get("quality_reason") or "Chưa xếp hạng"
    rows = []
    for symbol, series in ranks.items():
        seen = [r for r in series if r is not None]
        rows.append({"symbol": symbol, "ranks": series, "latest": series[-1] if series else None,
                     "mean": sum(seen) / len(seen) if seen else None, "ranked_sessions": len(seen),
                     "reasons": {str(k): v for k, v in reasons.get(symbol, {}).items()}})
    rows.sort(key=lambda r: (r["latest"] is None, r["latest"] or 0, r["symbol"]))
    return {"weights": weights, "foreign": foreign, "method": daily_rank.METHOD,
            "days": [{"id": _day_id(d), "label": f"{d[8:10]}/{d[5:7]}"} for d in days], "rows": rows}


def validation(source, weights="balanced"):
    """Forward check of the end-of-day score against the next session's return."""
    from src.analytics.validation import forward_check, verdict
    _require_daily(source, "Kiểm chứng")
    if weights not in daily_rank.WEIGHTS:
        raise ApiError("Cấu hình trọng số không hợp lệ.")
    result = forward_check(_daily_frame(), weights=(weights,))
    part = result["weights"][weights]
    return {"method": result["method"], "sessions": result["sessions"], "pairs": result["pairs"],
            "top_n": result["top_n"], "returns": result["returns"], "weights": weights,
            "weights_label": daily_rank.WEIGHT_LABELS[weights],
            "summary": {"ic": part["ic"], "spread": part["top_minus_bottom_pp"], "ic_close": part["ic_close"],
                        "spread_close": part["top_minus_bottom_close_pp"], "power": part["power"]},
            "factor_ic": part["factor_ic"], "series": part["pairs"], "verdict": verdict(part)}


def snapshot(source, run=None, point=None, weights="balanced", foreign="value", compare=None):
    if compare not in (None, "", *COMPARE):
        raise ApiError("Mốc so sánh không hợp lệ.")
    if source == "daily":
        if weights not in daily_rank.WEIGHTS or foreign not in ("value", "volume"):
            raise ApiError("Cấu hình trọng số hoặc khối ngoại không hợp lệ.")
        return _daily_snapshot(point, weights, foreign, compare)
    settings = load_settings()
    provider = load_provider_settings(settings.provider)
    if weights not in WEIGHTS:
        raise ApiError("Cấu hình trọng số không hợp lệ.")
    if foreign not in ("value", "volume"):
        raise ApiError("Cách tính khối ngoại không hợp lệ.")
    report = None
    if _is_journal(source):
        available = [r["id"] for r in runs(source)]  # ordered: newest store run / first sample first
        if run is not None and run not in available:
            raise ApiError("Lần thu thập không thuộc nguồn đã chọn.")
        run = run or (available[0] if available else None)
        if run is None:
            raise ApiError("Kho chưa có lần thu thập nào.")
        if not point and source == "demo-journal":
            data_points = [p["id"] for p in timeline(source, run) if p["kind"] == "data"]
            point = data_points[-1] if data_points else None
        report = _resolve_journal(source, run, point, settings.mode)
        frame = _journal_frame(report)
        as_of, data_source = report["as_of"], report["source"]
        connection_state = report["last_recorded_connection_state"]
        with SSIJournal(_journal_path(source)) as journal:
            last_recorded = journal.describe(run)["last_received_at"]
    else:
        events = _legacy_events(source)
        if not events:
            raise ApiError("Lần thu thập được chọn chưa có sự kiện.")
        moments = [p["id"] for p in timeline(source, run)]
        if not moments:
            raise ApiError("Chưa có snapshot cổ phiếu trong kho.")
        cutoff = now() if settings.mode == "live" and source == "store" else (point if point in moments else moments[-1])
        frame = state_at(events, cutoff, update_mode=recorded_update_mode(events, provider.update_mode))
        as_of, data_source, last_recorded = timestamp(cutoff).isoformat(), events[0]["source"], moments[-1]
        run = events[0]["run"]
        connection_state = "demo" if source == "demo-board" else "recorded"
    weight_map = WEIGHTS[weights]
    ranked = rank_groups(frame, weights=weight_map, semantics_verified=provider.semantics_verified,
                         foreign_basis=foreign) if not frame.empty else frame
    quality = {r["symbol"]: r for r in report["rows"]} if report else {}
    groups = {}
    for group in GROUPS:
        part = ranked[ranked["index_group"].eq(group)] if not ranked.empty else ranked
        rows = []
        for rec in part.to_dict("records"):
            q = quality.get(rec["symbol"], {})
            codes = q.get("reasons", [])
            kind, label = _status(codes, rec.get("quality_reason", ""))
            ranked_ok = rec.get("rank") is not None and _num(rec.get("rank")) is not None
            scores = {f: _num(rec.get(f"score_{f}")) for f in FACTOR_NAMES}
            if "CONNECTION_NOT_ACTIVE" in codes:
                # Missing fields and session are consequences of the gap, not separate findings.
                details = [REASON_TEXT["CONNECTION_NOT_ACTIVE"]]
                details += [REASON_TEXT["NO_BASELINE"]] if "NO_BASELINE" in codes else []
                details += ["Chưa rõ phiên (mất kết nối)"] if "SESSION_NOT_LO" in codes else []
            else:
                details = [REASON_TEXT.get(c, c) for c in codes] or ([rec["quality_reason"]] if rec.get("quality_reason") else [])
            rows.append({
                "symbol": rec["symbol"], "rank": int(rec["rank"]) if ranked_ok else None,
                "total": _num(rec.get("total_score")), "scores": scores,
                "contributions": {f: (scores[f] * weight_map[f] if scores[f] is not None else None) for f in FACTOR_NAMES},
                "raw": {**{k: _num(rec.get(k)) for k in ("momentum", "turnover", "spread_bps", "depth_vnd", "foreign_ratio",
                                                          "imbalance", "closePrice", "openPrice", "totalTradingVolume")},
                        "change_pct": None, "foreign_net_value": _net(rec.get("foreignBuyValue"), rec.get("foreignSellValue"))},
                "status": {"kind": "ranked" if ranked_ok else kind, "label": "Đã xếp hạng" if ranked_ok else label,
                           "details": [] if ranked_ok else details},
                "warnings": [WARNING_TEXT.get(w, w) for w in q.get("warnings", [])],
                "session": rec.get("session") or (q.get("trading_session") if q else None),
                "ages": {c: _age(q, f) for c, f in CLUSTERS.items()} if q else {},
                "explanation": rec.get("explanation") if ranked_ok else None,
            })
        rows.sort(key=lambda r: (r["rank"] is None, r["rank"] or 0, r["symbol"]))
        first = part.iloc[0] if len(part) else None
        groups[group] = {
            "members": len(rows), "ranked": sum(r["rank"] is not None for r in rows),
            "cohort_size": int(first["cohort_size"]) if first is not None and "cohort_size" in part else 0,
            "config_id": first.get("config_id") if first is not None else None,
            "cohort_id": first.get("cohort_id") if first is not None else None,
            "method": first.get("method_version") if first is not None else None,
            "usable": report["group_coverage"].get(group, {}).get("data_usable") if report else None,
            "rows": rows,
        }
    label, severity = CONNECTION.get(connection_state, (connection_state, "muted"))
    received = [timestamp(t) for r in (report["rows"] if report else []) for t in r.get("field_received_at", {}).values()]
    freshness = (timestamp(as_of) - max(received)).total_seconds() if received else None
    gaps = report.get("gaps", []) if report else []
    compare_info = None
    if compare:
        if report is not None:
            current_id = report["last_applied_event_id"]
            target = _compare_point(source, run, current_id, as_of, compare) if current_id else None
        else:
            target = _compare_point(source, run, None, as_of, compare, moments=moments)
        compare_info = {"mode": compare, "label": COMPARE[compare], "point": target, "as_of": None}
    result = {
        "source": data_source, "source_kind": source, "run": run, "as_of": as_of, "last_recorded": last_recorded,
        "mode": settings.mode, "synthetic": data_source == "synthetic",
        "verified": data_source == "synthetic" or bool(provider.semantics_verified),
        "scope_note": None if data_source == "synthetic" else FOREIGN_SCOPE_NOTE,
        "profile": report.get("profile") if report else None,
        "connection": {"state": connection_state, "label": label, "severity": severity,
                       "epoch": report.get("connection_epoch") if report else None},
        "freshness_seconds": freshness, "gaps": gaps[-5:],
        "policy": report.get("policy") if report else {"max_age_seconds": 60},
        "weights": {"id": weights, "label": WEIGHT_LABELS[weights], "values": weight_map},
        "foreign": foreign, "groups": groups, "compare": compare_info,
        "pulse": _pulse(groups.get("VN30", {}).get("rows", []), None, "giá mở cửa"),
    }
    if compare_info and compare_info["point"]:
        previous = snapshot(source, run, compare_info["point"], weights, foreign)
        compare_info["as_of"] = previous["as_of"]
        _attach_changes(result, previous)
    return result


# -- history and export ---------------------------------------------------------------------------

def history(source, run, point, symbol):
    """Recorded last-price points of one symbol up to the chosen moment."""
    series = []
    if source == "daily":
        frame = _daily_frame()
        part = frame[frame["symbol"] == symbol].sort_values("tradingDate")
        cutoff = str(point)[:10] if point else None
        for rec in part.to_dict("records"):
            if (cutoff is None or rec["tradingDate"] <= cutoff) and _num(rec.get("closePrice")) is not None:
                d = rec["tradingDate"]
                series.append({"at": _day_id(d), "label": f"{d[8:10]}/{d[5:7]}", "price": _num(rec["closePrice"])})
        return {"symbol": symbol, "points": series}
    if _is_journal(source):
        through = int(point) if point and str(point).isdigit() else None
        with SSIJournal(_journal_path(source)) as journal:
            for event in journal.events(run, through):
                if event["channel"] != "ssiDecoded":
                    continue
                payload = event["payload"]["payload"]
                if payload.get("symbol") == symbol and _num(payload.get("closePrice")) is not None:
                    series.append({"at": event["payload"].get("source_at") or event["received_at"], "price": _num(payload["closePrice"])})
    else:
        cutoff = timestamp(point) if point else None
        for e in _legacy_events(source):
            if e["channel"] == "stockInfo" and e["payload"].get("symbol") == symbol and (cutoff is None or timestamp(e["received_at"]) <= cutoff):
                if _num(e["payload"].get("closePrice")) is not None:
                    series.append({"at": e["received_at"], "price": _num(e["payload"]["closePrice"])})
    return {"symbol": symbol, "points": series[-300:]}


def export_csv(source, run=None, point=None, weights="balanced", foreign="value", group=None, compare=None):
    data = snapshot(source, run, point, weights, foreign, compare)
    out = io.StringIO()
    columns = ["source", "run", "as_of", "index_group", "symbol", "rank", "total_score",
               *[f"score_{f}" for f in FACTOR_NAMES], *[f"weight_{f}" for f in FACTOR_NAMES],
               "foreign_basis", "method_version", "config_id", "cohort_id", "status", "reasons", "warnings",
               "compare_as_of", "prev_rank", "rank_change", "total_change"]
    writer = csv.DictWriter(out, fieldnames=columns)
    writer.writeheader()
    for name, g in data["groups"].items():
        if group and name != group:
            continue
        for row in g["rows"]:
            writer.writerow({"source": data["source"], "run": data["run"], "as_of": data["as_of"], "index_group": name,
                             "symbol": row["symbol"], "rank": row["rank"], "total_score": row["total"],
                             **{f"score_{f}": row["scores"][f] for f in FACTOR_NAMES},
                             **{f"weight_{f}": data["weights"]["values"][f] for f in FACTOR_NAMES},
                             "foreign_basis": foreign, "method_version": g["method"], "config_id": g["config_id"],
                             "cohort_id": g["cohort_id"], "status": row["status"]["label"],
                             "reasons": " | ".join(row["status"]["details"]), "warnings": " | ".join(row["warnings"]),
                             "compare_as_of": (data["compare"] or {}).get("as_of"), "prev_rank": row.get("prev_rank"),
                             "rank_change": row.get("rank_change"), "total_change": row.get("total_change")})
    return "\ufeff" + out.getvalue()
