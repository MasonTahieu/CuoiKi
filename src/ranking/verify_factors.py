"""Generate a repeatable, offline comparison of the four ranking factors."""
import json

import pandas as pd

from src.config import PROJECT_ROOT
from src.finance.factors import factors
from src.ranking.engine import DEFAULT_WEIGHTS, FACTOR_NAMES, rank_groups


CONFIGURATIONS = {
    "value_balanced": ("value", DEFAULT_WEIGHTS),
    "value_momentum": ("value", dict(momentum=0.4, liquidity=0.2, foreign=0.2, imbalance=0.2)),
    "volume_balanced": ("volume", DEFAULT_WEIGHTS),
}


def hand_quote():
    return {
        "openPrice": 100, "closePrice": 110,
        "totalTradingValue": 10_000, "foreignBuyValue": 1_000, "foreignSellValue": 3_000,
        "totalTradingVolume": 400, "foreignBuyVolume": 120, "foreignSellVolume": 40,
        "bidPrice1": 99, "bidPrice2": 98, "bidPrice3": 97,
        "askPrice1": 101, "askPrice2": 102, "askPrice3": 103,
        "bidVol1": 200, "bidVol2": 200, "bidVol3": 200,
        "askVol1": 100, "askVol2": 100, "askVol3": 100,
    }


def verification_frame():
    rows = []
    for group, market in (("VN30", "HOSE"), ("HNX30", "HNX")):
        for i in range(11):
            # Different factor orders create tradeoffs while keeping all 11 rows eligible.
            if group == "VN30":
                liquidity = 10 - i
                value_order = (3*i + 2) % 11
                volume_order = (7*i + 3) % 11
                book = (2*i + 4) % 11
            else:
                liquidity = (7*i + 1) % 11
                value_order = 10 - i
                volume_order = (3*i + 4) % 11
                book = (2*i + 5) % 11
            price = 19_500 + 100*i
            turnover = (liquidity + 10) * 10_000_000
            volume = turnover // 20_000
            row = {
                "symbol": f"{market}TEST{i+1:02d}", "index_group": group, "marketCode": market,
                "source": "synthetic", "run": "synthetic-task4-v1",
                "as_of": "2026-11-05T10:00:00+07:00", "quality_reason": "",
                "openPrice": 20_000, "closePrice": price, "totalTradingValue": turnover,
                "totalTradingVolume": volume, "foreignBuyValue": turnover * (2*value_order + 5) // 100,
                "foreignSellValue": turnover * 15 // 100, "foreignBuyVolume": volume * (2*volume_order + 5) // 100,
                "foreignSellVolume": volume * 15 // 100,
            }
            for level in (1, 2, 3):
                distance = 50 * (10 - liquidity + level)
                row[f"bidPrice{level}"] = price - distance
                row[f"askPrice{level}"] = price + distance
                row[f"bidVol{level}"] = (liquidity + 10) * (10 + book)
                row[f"askVol{level}"] = (liquidity + 10) * (20 - book)
            rows.append(row)
    return pd.DataFrame(rows)


def compare_ranks(baseline, variant):
    before = baseline.set_index("symbol")["rank"]
    after = variant.set_index("symbol")["rank"]
    shift = (before - after).abs()
    top_before = before[before.le(3)].index.tolist()
    top_after = after[after.le(3)].index.tolist()
    return {
        "changed": int(shift.ne(0).sum()),
        "max_shift": int(shift.max()),
        "top_before": top_before,
        "top_after": top_after,
        "top_overlap": len(set(top_before) & set(top_after)),
    }


def main():
    output = PROJECT_ROOT / "evidence" / "task4"
    output.mkdir(parents=True, exist_ok=True)
    frame = verification_frame()
    quote = hand_quote()
    shallow = {key: value // 10 if key.startswith(("bidVol", "askVol")) else value for key, value in quote.items()}
    hand_cases = {
        "Giá trị, spread 2": factors(quote),
        "Giá trị, spread 1": factors({**quote, "bidPrice1": 99.5, "askPrice1": 100.5}),
        "Giá trị, độ sâu giảm 90%": factors(shallow),
        "Khối lượng, cùng snapshot": factors(quote, foreign_basis="volume"),
    }

    ranked = {}
    results = {}
    for name, (basis, weights) in CONFIGURATIONS.items():
        scored = rank_groups(frame, weights=weights, foreign_basis=basis)
        ranked[name] = scored
        columns = ["symbol", "index_group", "as_of", "foreign_ratio", "rank", "total_score",
                   "method_version", "config_id", "cohort_id", "cohort_size"]
        for factor in FACTOR_NAMES:
            score_column = f"score_{factor}"
            contribution_column = f"contribution_{factor}"
            scored[contribution_column] = scored[score_column] * weights[factor]
            columns.extend((score_column, contribution_column))
        results[name] = {"foreign_basis": basis, "weights": weights, "rows": scored[columns].to_dict("records")}

    comparisons = {}
    for group in ("VN30", "HNX30"):
        baseline = ranked["value_balanced"].loc[lambda rows: rows.index_group.eq(group)]
        comparisons[group] = {}
        for name in ("value_momentum", "volume_balanced"):
            variant = ranked[name].loc[lambda rows: rows.index_group.eq(group)]
            comparisons[group][name] = compare_ranks(baseline, variant)

    small = frame.drop(frame.index[:2])
    small_group_counts = rank_groups(small).groupby("index_group")["rank"].count().to_dict()
    evidence = {
        "source": "synthetic", "run": "synthetic-task4-v1",
        "hand_quote": quote, "hand_cases": hand_cases,
        "inputs": frame.to_dict("records"), "configurations": results,
        "comparisons": comparisons, "ranked_with_9_vn30_members": small_group_counts,
    }
    (output / "doi_chieu.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    lines = [
        "# Task 4 — Đối chiếu bốn yếu tố", "",
        "Dữ liệu giả lập gồm 11 mã mỗi nhóm. Các thứ tự yếu tố được thiết kế để kiểm tra sự đánh đổi khi chấm điểm.", "",
        "## Ca tính tay", "",
        "Giá cuối 110, mở cửa 100, tổng giá trị khớp 10.000. Giá mua 99/98/97, giá bán 101/102/103.",
        "Ba mức mua có 200 đơn vị mỗi mức, ba mức bán có 100 mỗi mức.",
        "Ngoại mua/bán theo giá trị là 1.000/3.000 và theo khối lượng là 120/40 trên tổng 400.", "",
        "| Ca | Động lượng | Spread (bps) | Độ sâu | Tỷ lệ ngoại | Cung–cầu |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, result in hand_cases.items():
        lines.append(f"| {name} | {result['momentum']:.2f}% | {result['spread_bps']:.2f} | "
                     f"{result['depth_vnd']:,.0f} | {result['foreign_ratio']:.2%} | {result['imbalance']:.4f} |")
    lines.extend([
        "", "## So sánh thứ hạng", "",
        "Thứ tự trọng số là động lượng, thanh khoản, khối ngoại, cung–cầu. Mốc so sánh dùng giá trị và 25/25/25/25.",
        "Các mã đồng hạng 3 đều được tính vào nhóm dẫn đầu.", "",
        "| Nhóm | Cấu hình so với mốc | Mã đổi hạng | Dịch hạng lớn nhất | Mã giữ vị trí trong nhóm dẫn đầu |",
        "|---|---|---:|---:|---:|",
    ])
    labels = {"value_momentum": "Giá trị, 40/20/20/20", "volume_balanced": "Khối lượng, 25/25/25/25"}
    for group, variants in comparisons.items():
        for name, result in variants.items():
            lines.append(f"| {group} | {labels[name]} | {result['changed']}/11 | {result['max_shift']} | "
                         f"{result['top_overlap']}/{len(result['top_before'])} |")
    lines.extend([
        "", "Khi giảm VN30 còn 9 mã, số mã được xếp hạng là "
        f"**{small_group_counts['VN30']} ở VN30** và **{small_group_counts['HNX30']} ở HNX30**.", "",
        "## Đóng góp vào tổng điểm của HOSETEST11", "",
        "| Cấu hình | Động lượng | Thanh khoản | Khối ngoại | Cung–cầu | Tổng | Hạng |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for name, scored in ranked.items():
        row = scored.loc[scored.symbol.eq("HOSETEST11")].iloc[0]
        contributions = " | ".join(f"{row[f'contribution_{factor}']:.2f}" for factor in FACTOR_NAMES)
        lines.append(f"| {labels.get(name, 'Giá trị, 25/25/25/25')} | {contributions} | "
                     f"{row['total_score']:.2f} | {row['rank']:.0f} |")
    lines.extend([
        "", "Tổng điểm là tổng bốn đóng góp. Mỗi đóng góp bằng điểm phân vị nhân trọng số.",
        "Mỗi so sánh dùng cùng tập mã tại cùng một mốc. Cấu hình theo khối lượng dùng cho kiểm chứng offline.",
        "", "Đầu vào, thứ hạng và đóng góp từng mã có trong bảng chi tiết. [Mở JSON](doi_chieu.json)",
        "Tái tạo bằng `python -X utf8 -m src.ranking.verify_factors`.",
        "", "Xem [đặc tả và điều kiện kiểm chứng SSI](../../docs/TASK_4_KIEM_CHUNG_BON_YEU_TO.md).", "",
    ])
    (output / "KET_QUA_MAU.md").write_text("\n".join(lines), encoding="utf-8")
    print(str(output / "KET_QUA_MAU.md"))


if __name__ == "__main__":
    main()
