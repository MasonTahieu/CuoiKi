"""Multi-session evaluation of the intraday screener and of the daily V3 summaries.

Nothing here forecasts returns. The questions are: is the data complete enough at each
checkpoint, how stable are ranks over time and across configurations, and which staleness
threshold is supported by the observed update intervals.
"""
from collections import Counter, defaultdict
from datetime import timedelta
import math

import numpy as np
import pandas as pd

from src.data.ssi_journal import SSIJournal
from src.data.ssi_quality import scheduled_session
from src.data.store import timestamp
from src.ranking.engine import rank_groups

CLUSTERS = {
    "trade": ("closePrice", "totalTradingVolume", "totalTradingValue"),
    "quote": ("bidPrice1", "askPrice1", "bidVol1", "askVol1"),
    "foreign": ("foreignBuyValue", "foreignSellValue"),
}
CANDIDATE_THRESHOLDS = (30, 60, 120, 300, 600)
MOMENTUM_WEIGHTS = {"momentum": .4, "liquidity": .2, "foreign": .2, "imbalance": .2}


def spearman(a, b):
    """Rank correlation on common keys; None when fewer than 3 pairs or no variance."""
    common = sorted(set(a) & set(b))
    if len(common) < 3:
        return None
    x = pd.Series([a[k] for k in common]).rank().to_numpy(float)
    y = pd.Series([b[k] for k in common]).rank().to_numpy(float)
    if np.std(x) == 0 or np.std(y) == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def top_overlap(a, b, k=5):
    top = lambda d: {s for s, _ in sorted(d.items(), key=lambda item: (-item[1], item[0]))[:k]}
    if len(a) < k or len(b) < k:
        return None
    return len(top(a) & top(b)) / k


def report_frame(report):
    """Replay report -> ranking input (same contract as the UI, without Streamlit)."""
    rows = []
    for row in report["rows"]:
        rows.append({**row["payload"], "symbol": row["symbol"], "marketCode": row["marketCode"],
                     "index_group": row["index_group"], "source": report["source"], "run": report["run"],
                     "as_of": report["as_of"], "session": row.get("trading_session"),
                     "quality_reason": ";".join(row["reasons"]), "warnings": ";".join(row["warnings"])})
    return pd.DataFrame(rows)


def _scores(ranked):
    out = defaultdict(dict)
    for _, row in ranked.iterrows():
        if isinstance(row.get("total_score"), float) and math.isfinite(row["total_score"]):
            out[row["index_group"]][row["symbol"]] = row["total_score"]
    return out


def update_intervals(path, run):
    """Gaps between consecutive source updates of each field cluster, per symbol, inside LO."""
    last, gaps, markets = {}, defaultdict(list), {}
    with SSIJournal(path) as journal:
        for event in journal.events(run):
            if event["channel"] == "universe":
                markets.update({m["symbol"]: m["marketCode"] for m in event["payload"].get("members", [])})
                continue
            if event["channel"] == "connection" and event["payload"].get("state") == "connecting":
                last.clear()  # a gap across a reconnect is a connection gap, not an update interval
                continue
            if event["channel"] != "ssiDecoded":
                continue
            item = event["payload"]
            payload, at = item["payload"], item.get("source_at")
            if not at or payload.get("symbol") not in markets:
                continue
            at = timestamp(at)
            if scheduled_session(markets[payload["symbol"]], at) != "LO":
                continue
            for cluster, fields in CLUSTERS.items():
                if any(field in payload for field in fields):
                    key = (payload["symbol"], cluster)
                    if key in last and at > last[key]:
                        gaps[cluster].append((at - last[key]).total_seconds())
                    last[key] = at
    result = {}
    for cluster, values in gaps.items():
        series = pd.Series(values)
        result[cluster] = {"gaps": len(values), **{f"p{q}": float(series.quantile(q / 100)) for q in (50, 90, 95, 99)},
                           "share_within": {str(t): float((series <= t).mean()) for t in CANDIDATE_THRESHOLDS}}
    return result


def evaluate_run(path, run, *, every_minutes=15, semantics_verified=False, exploratory=True):
    from src.ssi_api.replay import replay
    with SSIJournal(path) as journal:
        info = journal.describe(run)
    start, end = timestamp(info["first_received_at"]), timestamp(info["last_received_at"])
    checkpoints, at = [], start + timedelta(minutes=every_minutes)
    while at <= end:
        checkpoints.append(at)
        at += timedelta(minutes=every_minutes)
    if not checkpoints or checkpoints[-1] != end:
        checkpoints.append(end)
    verified = semantics_verified or exploratory
    points, previous = [], None
    for cut in checkpoints:
        report = replay(path, run, as_of=cut.isoformat())
        frame = report_frame(report)
        if frame.empty:
            continue
        base = rank_groups(frame, semantics_verified=verified)
        momentum = rank_groups(frame, weights=MOMENTUM_WEIGHTS, semantics_verified=verified)
        volume = rank_groups(frame, semantics_verified=verified, foreign_basis="volume")
        s_base, s_mom, s_vol = _scores(base), _scores(momentum), _scores(volume)
        point = {"as_of": cut.isoformat(), "groups": {}}
        for group, cov in report["group_coverage"].items():
            point["groups"][group] = {
                "members": cov["members"], "data_usable": cov["data_usable"],
                "ranked": len(s_base.get(group, {})),
                "reasons": dict(Counter(r for row in report["rows"] if row["index_group"] == group for r in row["reasons"])),
                "spearman_vs_previous": spearman(s_base.get(group, {}), previous.get(group, {})) if previous else None,
                "top5_overlap_vs_previous": top_overlap(s_base.get(group, {}), previous.get(group, {})) if previous else None,
                "spearman_momentum_weights": spearman(s_base.get(group, {}), s_mom.get(group, {})),
                "spearman_foreign_volume": spearman(s_base.get(group, {}), s_vol.get(group, {})),
            }
        points.append(point)
        previous = s_base
    return {"run": run, "source": info["source"], "first_received_at": start.isoformat(), "last_received_at": end.isoformat(),
            "checkpoints": points, "update_intervals": update_intervals(path, run),
            "exploratory_ranking": exploratory and not semantics_verified}


def summarize(runs):
    """Averages across runs/checkpoints per group: what share of the time ranking was possible."""
    rows = []
    for run in runs:
        for point in run["checkpoints"]:
            for group, g in point["groups"].items():
                rows.append({"run": run["run"], "as_of": point["as_of"], "group": group, **{k: v for k, v in g.items() if k != "reasons"}})
    frame = pd.DataFrame(rows)
    if frame.empty:
        return {}
    out = {}
    for group, part in frame.groupby("group"):
        mean = lambda col: float(part[col].dropna().mean()) if part[col].notna().any() else None
        out[group] = {"checkpoints": int(len(part)), "ranked_share": float((part["ranked"] > 0).mean()),
                      "usable_mean": mean("data_usable"), "spearman_vs_previous_mean": mean("spearman_vs_previous"),
                      "top5_overlap_mean": mean("top5_overlap_vs_previous"),
                      "spearman_momentum_weights_mean": mean("spearman_momentum_weights"),
                      "spearman_foreign_volume_mean": mean("spearman_foreign_volume")}
    return out


def evaluate_journal(path, *, every_minutes=15, semantics_verified=False, exploratory=True, source="ssi"):
    with SSIJournal(path) as journal:
        runs = [r["run"] for r in journal.runs(500) if r["source"] == source]
    evaluated = [evaluate_run(path, run, every_minutes=every_minutes, semantics_verified=semantics_verified,
                              exploratory=exploratory) for run in sorted(runs)]
    trading_days = sorted({timestamp(r["first_received_at"]).date().isoformat() for r in evaluated})
    return {"schema_version": "screener-session-eval-1", "source": source, "runs": len(evaluated),
            "trading_days": trading_days, "summary": summarize(evaluated), "details": evaluated,
            "note": ("Xếp hạng thăm dò: chưa bật SSI_SEMANTICS_VERIFIED nên chỉ dùng để đánh giá kỹ thuật, "
                     "không hiển thị như kết quả sản phẩm.") if exploratory and not semantics_verified else None}


def daily_factors(frame):
    """Daily context factors from securitiesSummary (no order book: imbalance is not available)."""
    data = frame.copy()
    for col in ("openPrice", "closePrice", "totalTradingValue", "foreignBuyValue", "foreignSellValue"):
        data[col] = pd.to_numeric(data[col], errors="coerce")
    valid = (data["openPrice"] > 0) & (data["closePrice"] > 0) & (data["totalTradingValue"] > 0)
    data["momentum"] = np.where(valid, 100 * (data["closePrice"] / data["openPrice"] - 1), np.nan)
    data["turnover"] = np.where(valid, data["totalTradingValue"], np.nan)
    data["foreign_ratio"] = np.where(valid & data["foreignBuyValue"].notna() & data["foreignSellValue"].notna(),
                                     (data["foreignBuyValue"] - data["foreignSellValue"]) / data["totalTradingValue"], np.nan)
    return data


def evaluate_daily(frame):
    """Rank persistence of each daily factor between consecutive sessions, per group."""
    if frame.empty:
        return {"sessions": 0}
    frame = frame[frame["index_group"].isin(["VN30", "HNX30"])]  # index-level rows are context, not members
    if frame.empty:
        return {"sessions": 0}
    data = daily_factors(frame)
    out = {"sessions": int(data["tradingDate"].nunique()), "trading_dates": sorted(data["tradingDate"].unique().tolist()), "groups": {}}
    for group, part in data.groupby("index_group"):
        days = sorted(part["tradingDate"].unique())
        persistence = {}
        for factor in ("momentum", "turnover", "foreign_ratio"):
            values = []
            for a, b in zip(days, days[1:]):
                left = part[part["tradingDate"] == a].set_index("symbol")[factor].dropna().to_dict()
                right = part[part["tradingDate"] == b].set_index("symbol")[factor].dropna().to_dict()
                rho = spearman(left, right)
                if rho is not None:
                    values.append(rho)
            persistence[factor] = {"pairs": len(values), "mean_spearman": float(np.mean(values)) if values else None}
        corr = part[["momentum", "turnover", "foreign_ratio"]].rank().corr()
        out["groups"][group] = {"symbols": int(part["symbol"].nunique()), "days": len(days),
                                "day_to_day_persistence": persistence,
                                "factor_rank_correlation": {f"{a}~{b}": (None if pd.isna(corr.loc[a, b]) else float(corr.loc[a, b]))
                                                            for a, b in (("momentum", "turnover"), ("momentum", "foreign_ratio"), ("turnover", "foreign_ratio"))},
                                "missing_share": {c: float(part[c].isna().mean()) for c in ("momentum", "turnover", "foreign_ratio")}}
    return out
