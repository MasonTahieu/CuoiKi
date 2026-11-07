"""End-of-day ranking from daily summaries (FastConnect V3 REST). Three factors, no order book.

This is a separate method ("daily-v1"), not the intraday four-factor screen: liquidity is matched
value only (no depth or spread) and the order-book imbalance factor does not exist at day level.
Missing inputs leave a stock unranked with a stated reason; nothing is reweighted.
"""
import hashlib
import json
import math

import pandas as pd

from src.ranking.engine import percentile

METHOD = "daily-v1"
FACTORS = ("momentum", "liquidity", "foreign")
WEIGHTS = {"balanced": {"momentum": 1 / 3, "liquidity": 1 / 3, "foreign": 1 / 3},
           "momentum": {"momentum": .5, "liquidity": .25, "foreign": .25}}
WEIGHT_LABELS = {"balanced": "Cân bằng 33/33/33", "momentum": "Ưu tiên động lượng 50/25/25"}
FOREIGN = {"value": ("foreignBuyValue", "foreignSellValue", "totalTradingValue"),
           "volume": ("foreignBuyVolume", "foreignSellVolume", "totalTradingVolume")}


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def daily_factors(row, foreign="value"):
    """Raw factors for one stock-day, or (None, reason)."""
    open_, close, value = _num(row.get("openPrice")), _num(row.get("closePrice")), _num(row.get("totalTradingValue"))
    if not open_ or not close or open_ <= 0 or close <= 0:
        return None, "Thiếu giá mở cửa hoặc đóng cửa"
    if not value or value <= 0:
        return None, "Không có giá trị khớp trong phiên"
    buy_key, sell_key, total_key = FOREIGN[foreign]
    buy, sell, total = _num(row.get(buy_key)), _num(row.get(sell_key)), _num(row.get(total_key))
    if buy is None or sell is None:
        return None, "Thiếu dữ liệu khối ngoại (SSI trả trống)"
    if not total or total <= 0:
        return None, "Không có mẫu số khối ngoại"
    ratio = (buy - sell) / total
    if abs(ratio) > 1:
        return None, "Tỷ lệ khối ngoại vượt phạm vi; cần kiểm tra đơn vị"
    return {"momentum": 100 * (close / open_ - 1), "turnover": value, "foreign_ratio": ratio,
            "foreign_net": buy - sell}, None


def rank_daily(rows, weights="balanced", foreign="value", min_cohort=10):
    """rows: daily summary dicts of ONE group and ONE trading date. Returns a DataFrame."""
    if weights not in WEIGHTS or foreign not in FOREIGN:
        raise ValueError("Cấu hình trọng số hoặc khối ngoại không hợp lệ.")
    weight_map = WEIGHTS[weights]
    records = []
    for row in rows:
        raw, reason = daily_factors(row, foreign)
        records.append({**row, **(raw or {}), "quality_reason": reason or ""})
    frame = pd.DataFrame(records)
    if frame.empty:
        return frame
    for name in FACTORS:
        frame[f"score_{name}"] = float("nan")
    frame["total_score"], frame["rank"] = float("nan"), float("nan")
    valid = frame.index[frame["quality_reason"].eq("")]
    cohort = sorted(frame.loc[valid, "symbol"].tolist())
    frame["method_version"] = METHOD
    frame["config_id"] = hashlib.sha256(json.dumps({"method": METHOD, "weights": weight_map, "foreign": foreign,
                                                    "min_cohort": min_cohort}, sort_keys=True).encode()).hexdigest()[:12]
    frame["cohort_id"] = hashlib.sha256(json.dumps(cohort).encode()).hexdigest()[:12]
    frame["cohort_size"] = len(valid)
    if len(valid) < min_cohort:
        frame.loc[valid, "quality_reason"] = f"chỉ có {len(valid)}/{min_cohort} mã hợp lệ; chưa xếp hạng"
        return frame
    view = frame.loc[valid]
    frame.loc[valid, "score_momentum"] = percentile(view["momentum"])
    frame.loc[valid, "score_liquidity"] = percentile(view["turnover"])
    frame.loc[valid, "score_foreign"] = percentile(view["foreign_ratio"])
    frame.loc[valid, "total_score"] = sum(frame.loc[valid, f"score_{k}"] * v for k, v in weight_map.items()).round(10)
    frame.loc[valid, "rank"] = frame.loc[valid, "total_score"].rank(method="min", ascending=False)
    return frame
