import pandas as pd
import pytest

from src.finance.factors import factors
from src.ranking.engine import rank_groups, rank_snapshot
from src.ranking.verify_factors import CONFIGURATIONS, hand_quote, verification_frame


def test_hand_calculation_has_opposite_foreign_signs_for_the_two_methods():
    value = factors(hand_quote())
    volume = factors(hand_quote(), foreign_basis="volume")
    assert value["momentum"] == pytest.approx(10)
    assert value["foreign_net_vnd"] == -2_000
    assert value["foreign_ratio"] == pytest.approx(-0.2)
    assert volume["foreign_net_volume"] == 80
    assert volume["foreign_ratio"] == pytest.approx(0.2)
    for name in ("momentum", "turnover", "spread_bps", "depth_vnd", "imbalance"):
        assert value[name] == volume[name]
    assert value["imbalance"] == pytest.approx(1/3)


def test_liquidity_scores_narrow_spread_and_large_depth_in_the_correct_direction():
    wide = hand_quote()
    narrow = {**wide, "bidPrice1": 99.5, "askPrice1": 100.5}
    shallow = {key: value // 10 if key.startswith(("bidVol", "askVol")) else value for key, value in wide.items()}
    context = {"source": "synthetic", "as_of": "2026-11-05T10:00:00+07:00", "quality_reason": ""}
    frame = pd.DataFrame([{**context, **quote, "symbol": symbol}
                          for symbol, quote in (("WIDE", wide), ("NARROW", narrow), ("SHALLOW", shallow))])
    rows = rank_snapshot(frame, min_cohort=3).set_index("symbol")
    assert rows.loc["WIDE", "spread_bps"] == 200
    assert rows.loc["NARROW", "spread_bps"] == 100
    assert rows.loc["WIDE", "depth_vnd"] == 89_400
    assert rows.loc["NARROW", "depth_vnd"] == 89_450
    assert rows.loc["SHALLOW", "depth_vnd"] == 8_940
    # Turnover ties at 50. The two 200 bps rows tie at 25 on spread.
    assert rows.loc[["NARROW", "WIDE", "SHALLOW"], "score_liquidity"].tolist() == pytest.approx(
        [250/3, 125/3, 75/3])


@pytest.mark.parametrize("field,value,message", [
    ("foreignBuyVolume", None, "foreignBuyVolume"),
    ("foreignSellVolume", -1, "foreignSellVolume"),
    ("totalTradingVolume", 0, "totalTradingVolume"),
    ("totalTradingVolume", float("inf"), "totalTradingVolume"),
    ("foreignBuyVolume", 999_999, "vượt phạm vi"),
])
def test_volume_method_excludes_bad_row_without_switching_to_value(field, value, message):
    frame = verification_frame()
    frame[field] = frame[field].astype(float)
    frame.loc[0, field] = value
    baseline = rank_groups(frame).set_index("symbol")
    volume = rank_groups(frame, foreign_basis="volume").set_index("symbol")
    assert baseline.loc["HOSETEST01", "rank"] >= 1
    invalid = volume.loc["HOSETEST01"]
    assert pd.isna(invalid["rank"])
    assert message in invalid["quality_reason"]
    assert volume.loc[volume.index_group.eq("VN30"), "rank"].count() == 10
    assert volume.loc[volume.index_group.eq("HNX30"), "rank"].count() == 11


def test_volume_method_uses_its_own_fields_and_validates_configuration():
    quote = hand_quote()
    quote.pop("foreignBuyValue")
    quote.pop("foreignSellValue")
    assert factors(quote, foreign_basis="volume")["foreign_ratio"] == pytest.approx(0.2)
    with pytest.raises(ValueError, match="foreignBuyValue"):
        factors(quote)
    with pytest.raises(ValueError, match="value hoặc volume"):
        rank_groups(pd.DataFrame(), foreign_basis="automatic")


def test_weights_and_foreign_basis_change_expected_score_on_a_fixed_cohort():
    frame = verification_frame()
    results = {}
    for name, (basis, weights) in CONFIGURATIONS.items():
        ranked = rank_groups(frame, weights=weights, foreign_basis=basis).set_index("symbol")
        results[name] = ranked.loc["HOSETEST11"]
        assert ranked.groupby("index_group")["rank"].count().to_dict() == {"HNX30": 11, "VN30": 11}
    balanced, momentum, volume = results.values()
    assert balanced[["score_momentum", "score_liquidity", "score_foreign", "score_imbalance"]].tolist() == [100, 0, 100, 20]
    assert volume[["score_momentum", "score_liquidity", "score_foreign", "score_imbalance"]].tolist() == [100, 0, 70, 20]
    assert [row["total_score"] for row in results.values()] == [55, 64, 47.5]
    assert len({row["cohort_id"] for row in results.values()}) == 1
    assert len({row["config_id"] for row in results.values()}) == 3
    assert balanced["method_version"] == momentum["method_version"] == "intraday-v1"
    assert volume["method_version"] == "intraday-foreign-volume-v1"
    assert pd.isna(volume["foreign_net_vnd"])


def test_small_vn30_group_does_not_block_hnx30_and_ssi_gate_still_applies():
    frame = verification_frame().iloc[2:].copy()
    ranked = rank_groups(frame, foreign_basis="volume")
    assert ranked.groupby("index_group")["rank"].count().to_dict() == {"HNX30": 11, "VN30": 0}
    frame["source"] = "ssi"
    locked = rank_groups(frame, foreign_basis="volume")
    assert locked["rank"].isna().all()
    assert locked["quality_reason"].str.contains("chưa xác minh ngữ nghĩa/đơn vị SSI").all()
