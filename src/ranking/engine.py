"""Same-cohort percentile ranking, missing data never silently reweighted."""
import hashlib
import json
import math
import pandas as pd
from src.finance.factors import FOREIGN_FIELDS, factors

FACTOR_NAMES = ["momentum", "liquidity", "foreign", "imbalance"]
DEFAULT_WEIGHTS = dict.fromkeys(FACTOR_NAMES, 0.25)
METHOD = "intraday-v1"
VOLUME_METHOD = "intraday-foreign-volume-v1"


def percentile(values, higher=True):
    if len(values) < 2:
        return pd.Series(float("nan"), index=values.index)
    if values.nunique() == 1:
        return pd.Series(50., index=values.index)
    return 100 * (values.rank(method="average", ascending=higher) - 1) / (len(values)-1)


def rank_snapshot(frame, weights=None, semantics_verified=False, min_cohort=10, *, foreign_basis="value"):
    if foreign_basis not in FOREIGN_FIELDS:
        raise ValueError("Chọn yếu tố ngoại theo value hoặc volume.")
    method = METHOD if foreign_basis == "value" else VOLUME_METHOD
    weights = DEFAULT_WEIGHTS if weights is None else weights
    if (set(weights) != set(FACTOR_NAMES) or any(not math.isfinite(v) or v < 0 for v in weights.values())
            or not math.isclose(sum(weights.values()), 1, abs_tol=1e-8)):
        raise ValueError("Bốn trọng số phải hữu hạn, không âm và có tổng bằng 1.")
    if min_cohort < 2:
        raise ValueError("Nhóm so sánh cần ít nhất hai mã.")
    result = frame.copy()
    if result.empty:
        return result
    if "index_group" in result and result["index_group"].nunique()!=1:
        raise ValueError("Chấm điểm theo nhóm bằng rank_groups.")
    if result["symbol"].duplicated().any() or result["as_of"].nunique() != 1 or result["source"].nunique() != 1:
        raise ValueError("Snapshot phải cùng mốc, cùng nguồn và không trùng mã.")
    for name in FACTOR_NAMES:
        result[f"score_{name}"] = float("nan")
    for key in ("momentum", "turnover", "spread_bps", "depth_vnd", "foreign_net_vnd", "foreign_ratio", "imbalance"):
        result[key] = float("nan")
    if foreign_basis == "volume":
        result["foreign_net_volume"] = float("nan")
    result["total_score"], result["rank"] = float("nan"), float("nan")
    for idx, row in result.iterrows():
        if row["quality_reason"]:
            continue
        if row["source"] != "synthetic" and not semantics_verified:
            result.at[idx, "quality_reason"] = f"chưa xác minh ngữ nghĩa/đơn vị {row['source'].upper()} tại P1"
            continue
        try:
            for key, value in factors(row, foreign_basis=foreign_basis).items():
                result.at[idx, key] = value
        except (ValueError, TypeError, KeyError) as exc:
            result.at[idx, "quality_reason"] = str(exc)
    valid = result.index[result["quality_reason"].eq("")]
    cohort = sorted(result.loc[valid, "symbol"].tolist())
    group=result["index_group"].iloc[0] if "index_group" in result else "VN30"
    configuration = {"method": method, "weights": weights, "min_cohort": min_cohort, "index_group":group}
    result["method_version"] = method
    result["config_id"] = hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()[:12]
    result["cohort_id"] = hashlib.sha256(json.dumps(cohort).encode()).hexdigest()[:12]
    result["cohort_size"] = len(valid)
    if len(valid) < min_cohort:
        result.loc[valid, "quality_reason"] = f"chỉ có {len(valid)}/{min_cohort} mã hợp lệ; chưa xếp hạng"
        return result
    view = result.loc[valid]
    result.loc[valid, "score_momentum"] = percentile(view["momentum"])
    result.loc[valid, "score_liquidity"] = (percentile(view["turnover"]) + percentile(view["depth_vnd"]) + percentile(view["spread_bps"], False))/3
    result.loc[valid, "score_foreign"] = percentile(view["foreign_ratio"])
    result.loc[valid, "score_imbalance"] = percentile(view["imbalance"])
    result.loc[valid, "total_score"] = sum(result.loc[valid, f"score_{k}"]*v for k,v in weights.items())
    # Avoid assigning different ranks to mathematically tied floating-point sums.
    result.loc[valid, "total_score"] = result.loc[valid, "total_score"].round(10)
    result.loc[valid, "rank"] = result.loc[valid, "total_score"].rank(method="min", ascending=False)
    result["explanation"] = "Chưa đủ điều kiện xếp hạng"
    labels = {"momentum":"động lượng", "liquidity":"thanh khoản", "foreign":"dòng tiền ngoại", "imbalance":"cung–cầu"}
    for idx in valid:
        best = max(FACTOR_NAMES, key=lambda k: result.at[idx, f"score_{k}"])
        worst = min(FACTOR_NAMES, key=lambda k: result.at[idx, f"score_{k}"])
        result.at[idx, "explanation"] = f"Điểm mạnh tương đối: {labels[best]}; thấp nhất: {labels[worst]}."
    return result.sort_values(["rank", "symbol"], na_position="last")


def rank_groups(frame, **kwargs):
    if frame.empty or "index_group" not in frame:
        return rank_snapshot(frame, **kwargs)
    return pd.concat([rank_snapshot(group, **kwargs) for _,group in frame.groupby("index_group",sort=True)])
