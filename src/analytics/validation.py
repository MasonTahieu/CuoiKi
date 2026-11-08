"""Next-session check of the end-of-day score: does today's rank line up with the next session's return?

Nothing is fitted here, so this is a forward check, not an out-of-sample test of an estimated model.
Weights were chosen before this was first computed and are not tuned on it.

- Score on day t uses only day-t summaries (src.ranking.daily).
- Main return: open to close of day t+1. The score exists only after day t closes, so the close of
  day t cannot be traded on it; counting from there would credit the overnight gap to the score.
- Comparison return: SSI's ``priceChangePercent`` of day t+1 (close to close in the data seen so far).
  ``refPrice`` is empty in the feed and no ex-rights day has occurred in the sample, so how this
  field behaves on such a day is not verified.
- Per pair of consecutive sessions: Spearman rank IC, and the mean return of the top 5 minus bottom 5.
- Across pairs: mean, sample standard deviation, t-statistic, share of positive pairs, and the
  smallest mean IC this sample could tell apart from zero (|t| = 2).

A mean IC near zero means "no evidence yet", not "proven to have no predictive power".
"""
import math

import numpy as np
import pandas as pd

from src.ranking.daily import WEIGHTS, rank_daily

FACTOR_COLUMNS = {"momentum": "momentum", "liquidity": "turnover", "foreign": "foreign_ratio"}
TOP_N = 5
RETURN_LABELS = {"tradable": "mở cửa → đóng cửa của phiên t+1 (mua được sau khi có điểm)",
                 "close": "priceChangePercent của phiên t+1 do SSI tính (gồm cả chênh lệch qua đêm, không mua kịp)"}


def _stats(values):
    values = [v for v in values if v is not None and math.isfinite(v)]
    n = len(values)
    if n == 0:
        return {"pairs": 0, "mean": None, "sd": None, "t": None, "positive_share": None}
    mean = float(np.mean(values))
    sd = float(np.std(values, ddof=1)) if n > 1 else None
    t = mean / (sd / math.sqrt(n)) if sd else None
    return {"pairs": n, "mean": mean, "sd": sd, "t": t, "positive_share": float(np.mean([v > 0 for v in values]))}


def _spearman(a, b):
    if len(a) < 3 or a.nunique() < 2 or b.nunique() < 2:
        return None
    return float(a.rank().corr(b.rank()))


def _spread(scored, column, top_n):
    if len(scored) < 2 * top_n:
        return None
    return float(scored.nlargest(top_n, "total_score")[column].mean()
                 - scored.nsmallest(top_n, "total_score")[column].mean())


def power(ic, target=0.05):
    """Smallest detectable mean IC at |t| = 2, and the sessions needed to detect ``target``."""
    if not ic["sd"] or not ic["pairs"]:
        return {"detectable_ic": None, "target_ic": target, "sessions_for_target": None}
    return {"detectable_ic": 2 * ic["sd"] / math.sqrt(ic["pairs"]), "target_ic": target,
            "sessions_for_target": math.ceil((2 * ic["sd"] / target) ** 2) + 1}


def adjustment_check(data, tolerance_pp=0.3):
    """How far SSI's priceChangePercent departs from plain close-to-close: large gaps mark possible ex-rights days."""
    ordered = data.sort_values(["symbol", "tradingDate"])
    plain = 100 * (ordered["closePrice"] / ordered.groupby("symbol")["closePrice"].shift(1) - 1)
    gap = (ordered["priceChangePercent"] - plain).abs().dropna()
    flagged = ordered.loc[gap[gap > tolerance_pp].index, ["symbol", "tradingDate"]].to_dict("records")
    ref = pd.to_numeric(data["refPrice"], errors="coerce") if "refPrice" in data else pd.Series(dtype=float)
    return {"tolerance_pp": tolerance_pp, "compared": int(len(gap)), "flagged": flagged, "ref_price_present": int(ref.notna().sum())}


def forward_check(frame, group="VN30", weights=tuple(WEIGHTS), top_n=TOP_N):
    """frame: daily summary rows (read_daily). Returns per-pair results and summaries per weight set."""
    data = frame[frame["index_group"] == group].copy()
    for column in ("openPrice", "closePrice", "priceChangePercent"):
        data[column] = pd.to_numeric(data[column], errors="coerce") if column in data else float("nan")
    tradable = 100 * (data["closePrice"] / data["openPrice"].where(data["openPrice"] > 0) - 1)
    data["tradable_return"] = tradable.where(data["closePrice"] > 0)
    days = sorted(data["tradingDate"].unique())
    out = {"method": "next-session-rank-ic-v2", "group": group, "sessions": len(days),
           "pairs": max(0, len(days) - 1), "top_n": top_n, "returns": RETURN_LABELS,
           "adjustment": adjustment_check(data), "weights": {}}
    for name in weights:
        rows, factor_ic = [], {f: [] for f in FACTOR_COLUMNS}
        for today, nxt in zip(days, days[1:]):
            ranked = rank_daily(data[data["tradingDate"] == today].to_dict("records"), weights=name)
            ranked = ranked.drop(columns=["tradable_return", "priceChangePercent"], errors="ignore").set_index("symbol")
            future = data[data["tradingDate"] == nxt].set_index("symbol")[["tradable_return", "priceChangePercent"]]
            joined = ranked.join(future, how="inner")
            scored = joined.dropna(subset=["total_score", "tradable_return"])
            against_close = joined.dropna(subset=["total_score", "priceChangePercent"])
            for factor, column in FACTOR_COLUMNS.items():
                part = joined.dropna(subset=[column, "tradable_return"]) if column in joined else joined.iloc[0:0]
                factor_ic[factor].append(_spearman(part[column], part["tradable_return"]) if len(part) else None)
            rows.append({"date": today, "next_date": nxt, "ranked": int(len(scored)),
                         "ic": _spearman(scored["total_score"], scored["tradable_return"]),
                         "top_minus_bottom_pp": _spread(scored, "tradable_return", top_n),
                         "ic_close": _spearman(against_close["total_score"], against_close["priceChangePercent"]),
                         "top_minus_bottom_close_pp": _spread(against_close, "priceChangePercent", top_n)})
        ic = _stats([r["ic"] for r in rows])
        out["weights"][name] = {"pairs": rows, "ic": ic, "power": power(ic),
                                "top_minus_bottom_pp": _stats([r["top_minus_bottom_pp"] for r in rows]),
                                "ic_close": _stats([r["ic_close"] for r in rows]),
                                "top_minus_bottom_close_pp": _stats([r["top_minus_bottom_close_pp"] for r in rows]),
                                "factor_ic": {f: _stats(v) for f, v in factor_ic.items()}}
    return out


def _fmt(value, digits=3, sign=True):
    if value is None:
        return "—"
    text = f"{value:+.{digits}f}" if sign else f"{value:.{digits}f}"
    return text.replace(".", ",").replace("-", "−")


def verdict(summary):
    """One honest sentence for the report and the page."""
    ic = summary["ic"]
    if not ic["pairs"]:
        return "Chưa đủ phiên để kiểm tra."
    stats = f"IC trung bình {_fmt(ic['mean'])}, t = {_fmt(ic['t'], 2)}, {ic['pairs']} cặp phiên"
    if ic["t"] is not None and abs(ic["t"]) >= 2:
        sign = "cùng chiều" if ic["mean"] > 0 else "ngược chiều"
        return f"Điểm có liên hệ {sign} với lợi suất phiên sau ({stats}), nhưng mẫu còn nhỏ nên cần thêm phiên để xác nhận."
    detectable = summary.get("power", {}).get("detectable_ic")
    limit = f" Với cỡ mẫu này chỉ phân biệt được IC từ khoảng {_fmt(detectable, 2, sign=False)} trở lên." if detectable else ""
    return (f"Chưa có bằng chứng điểm liên hệ với lợi suất phiên sau ({stats}).{limit} "
            "Điểm dùng để thu hẹp danh sách, không phải tín hiệu mua bán.")


def adjustment_note(info):
    ref = "`refPrice` trống ở mọi dòng" if not info["ref_price_present"] else f"`refPrice` có ở {info['ref_price_present']} dòng"
    limit = _fmt(info["tolerance_pp"], 1, sign=False)
    if not info["flagged"]:
        return (f"- **Điều chỉnh quyền:** {ref} và trong {info['compared']} dòng so sánh chưa có dòng nào `priceChangePercent` lệch quá "
                f"{limit} điểm % so với đóng cửa/đóng cửa, nên cách trường này xử lý ngày giao dịch không hưởng quyền chưa được kiểm chứng.")
    cases = ", ".join(f"{c['symbol']} {c['tradingDate']}" for c in info["flagged"][:10])
    return (f"- **Điều chỉnh quyền:** {ref}. Có {len(info['flagged'])}/{info['compared']} dòng `priceChangePercent` lệch quá {limit} điểm % "
            f"so với đóng cửa/đóng cửa ({cases}). Cần đối chiếu với lịch giao dịch không hưởng quyền.")


def write_evidence(result, folder):
    """KIEM_TRA_PHIEN_KE_TIEP.md and a per-pair CSV, regenerated by `python -m src.cli evaluate-v3`."""
    folder.mkdir(parents=True, exist_ok=True)
    balanced = result["weights"]["balanced"]
    pd.DataFrame(balanced["pairs"]).to_csv(folder / "kiem_tra_phien_ke_tiep.csv", index=False, encoding="utf-8")
    labels = {"balanced": "Cân bằng 33/33/33", "momentum": "Ưu tiên động lượng 50/25/25"}
    factor_labels = {"momentum": "Động lượng", "liquidity": "Thanh khoản", "foreign": "Dòng tiền ngoại"}
    head = ["| Cấu hình | IC trung bình | Độ lệch chuẩn | t | Tỷ lệ cặp IC > 0 | Top 5 − Bottom 5 (điểm %) | t |",
            "|---|---:|---:|---:|---:|---:|---:|"]

    def table(ic_key, spread_key):
        rows = []
        for name, part in result["weights"].items():
            ic, spread = part[ic_key], part[spread_key]
            share = "—" if ic["positive_share"] is None else f"{ic['positive_share']:.0%}"
            rows.append(f"| {labels.get(name, name)} | {_fmt(ic['mean'])} | {_fmt(ic['sd'], sign=False)} | {_fmt(ic['t'], 2)} | "
                        f"{share} | {_fmt(spread['mean'], 2)} | {_fmt(spread['t'], 2)} |")
        return rows

    power_info = balanced["power"]
    lines = ["# Kiểm tra phiên kế tiếp: điểm cuối ngày và lợi suất phiên sau", "",
             f"Dữ liệu SSI thật, rổ {result['group']}, **{result['sessions']} phiên**, {result['pairs']} cặp phiên liên tiếp. "
             "Không có tham số nào được ước lượng. Trọng số chọn trước khi tính phép đo này. Điểm phiên t chỉ dùng dữ liệu phiên t.", "",
             "## Lợi suất mua được", "", f"Tính từ {result['returns']['tradable']}.", "", *head,
             *table("ic", "top_minus_bottom_pp"), "",
             "## So sánh: tính cả chênh lệch qua đêm", "", f"Tính theo {result['returns']['close']}.", "", *head,
             *table("ic_close", "top_minus_bottom_close_pp"), "",
             "## IC của từng yếu tố (cấu hình cân bằng, lợi suất mua được)", "", "| Yếu tố | IC trung bình | t |", "|---|---:|---:|"]
    for factor, stats in balanced["factor_ic"].items():
        lines.append(f"| {factor_labels[factor]} | {_fmt(stats['mean'])} | {_fmt(stats['t'], 2)} |")
    lines += ["", "## Kết luận", "", verdict(balanced), "",
              f"- **Độ nhạy:** mẫu này chỉ phân biệt được IC trung bình từ khoảng {_fmt(power_info['detectable_ic'], 2, sign=False)} trở lên. "
              f"Muốn phát hiện IC {_fmt(power_info['target_ic'], 2, sign=False)} cần khoảng {power_info['sessions_for_target'] or '—'} phiên. "
              "Vì vậy kết quả là \"chưa có bằng chứng\", không phải \"đã chứng minh không dự báo được\".",
              "- **Kiểm định nhiều lần:** có nhiều phép đo trên cùng mẫu, nên một giá trị |t| vừa trên 2 chưa đủ để coi là phát hiện.",
              adjustment_note(result["adjustment"]),
              "- Kết quả không thay đổi cách chấm điểm. Sản phẩm không trình bày điểm như xác suất tăng giá.", "",
              "Chi tiết từng cặp phiên: [kiem_tra_phien_ke_tiep.csv](kiem_tra_phien_ke_tiep.csv). "
              "Tạo lại: `python -X utf8 -m src.cli evaluate-v3`.", ""]
    (folder / "KIEM_TRA_PHIEN_KE_TIEP.md").write_text("\n".join(lines), encoding="utf-8")
