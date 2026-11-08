"""Next-session check (src.analytics.validation). Offline, synthetic daily rows."""
import pandas as pd
import pytest

from src.analytics.validation import adjustment_note, forward_check, power, verdict, write_evidence


def rows(days=4, size=12, momentum=lambda i, d: 0.2 * i, close_change=lambda i, d: 0.0):
    """Higher i -> higher turnover and foreign ratio. ``momentum`` sets open-to-close of each day."""
    out = []
    for d in range(days):
        for i in range(size):
            out.append({"symbol": f"S{i:02d}", "index_group": "VN30", "tradingDate": f"2026-11-0{d + 1}",
                        "openPrice": 10_000, "closePrice": 10_000 * (1 + momentum(i, d) / 100),
                        "totalTradingValue": 1e9 * (i + 1), "foreignBuyValue": 1e7 * i, "foreignSellValue": 1e7,
                        "priceChangePercent": close_change(i, d)})
    out.append({"symbol": "VN30", "index_group": "INDEX", "tradingDate": "2026-11-01", "closePrice": 1800.0})
    return pd.DataFrame(out)


def test_ordering_kept_next_session_gives_ic_one_and_positive_spread():
    result = forward_check(rows())
    part = result["weights"]["balanced"]
    assert result["sessions"] == 4 and result["pairs"] == 3
    assert [p["ic"] for p in part["pairs"]] == pytest.approx([1, 1, 1])
    assert part["ic"]["mean"] == pytest.approx(1) and part["ic"]["positive_share"] == 1
    assert part["top_minus_bottom_pp"]["mean"] == pytest.approx(0.2 * 7)  # mean(7..11) - mean(0..4)
    assert all(p["ranked"] == 12 for p in part["pairs"])


def test_reversed_ordering_is_reported_as_negative_not_hidden():
    flips = lambda i, d: 0.2 * i if d % 2 == 0 else -0.2 * i
    part = forward_check(rows(days=2, momentum=flips))["weights"]["balanced"]
    assert part["ic"]["mean"] == pytest.approx(-1)


def test_return_comes_from_the_next_session_only():
    # Same-day open-to-close matches the score perfectly, the next day is the reverse: a look-ahead
    # bug (using same-day returns) would report +1, the correct check reports -1.
    result = forward_check(rows(days=2, momentum=lambda i, d: 0.2 * i if d == 0 else -0.2 * i))
    assert result["weights"]["balanced"]["pairs"][0]["ic"] == pytest.approx(-1)


def test_tradable_return_is_separate_from_the_close_to_close_figure():
    # Next session moves up from the close for the high scorers, then falls back after the open:
    # counting from the close looks good, what could actually be bought does not.
    frame = rows(days=2, momentum=lambda i, d: 0.2 * i if d == 0 else -0.2 * i, close_change=lambda i, d: 0.1 * i)
    part = forward_check(frame)["weights"]["balanced"]
    assert part["pairs"][0]["ic"] == pytest.approx(-1)
    assert part["pairs"][0]["ic_close"] == pytest.approx(1)
    assert part["ic_close"]["pairs"] == part["top_minus_bottom_close_pp"]["pairs"] == 1


def test_adjustment_note_follows_the_data(tmp_path):
    frame = rows(days=3, momentum=lambda i, d: 0.0, close_change=lambda i, d: 0.0)
    clean = forward_check(frame)["adjustment"]
    assert clean["flagged"] == [] and clean["compared"] == 24 and clean["ref_price_present"] == 0
    assert "chưa được kiểm chứng" in adjustment_note(clean)
    frame.loc[(frame["symbol"] == "S03") & (frame["tradingDate"] == "2026-11-03"), "priceChangePercent"] = 4.0
    flagged = forward_check(frame)["adjustment"]
    assert flagged["flagged"] == [{"symbol": "S03", "tradingDate": "2026-11-03"}]
    assert "S03 2026-11-03" in adjustment_note(flagged) and "chưa được kiểm chứng" not in adjustment_note(flagged)


def test_power_states_what_the_sample_can_detect():
    assert power({"pairs": 16, "sd": 0.2})["detectable_ic"] == pytest.approx(0.1)
    assert power({"pairs": 16, "sd": 0.2})["sessions_for_target"] == 65  # (2 * .2 / .05)^2 pairs + 1 session
    assert power({"pairs": 1, "sd": None})["detectable_ic"] is None


def test_verdict_says_no_evidence_yet_rather_than_no_power(tmp_path):
    flat = forward_check(rows(momentum=lambda i, d: 0.2 * i if d == 0 else 0.0))["weights"]["balanced"]
    assert flat["ic"]["pairs"] == 0 and verdict(flat) == "Chưa đủ phiên để kiểm tra."
    noisy = forward_check(rows(days=9, momentum=lambda i, d: (((i * 7 + d * d * 3) % 5) - 2.0) * 0.3))["weights"]["balanced"]
    if abs(noisy["ic"]["t"]) < 2:
        assert verdict(noisy).startswith("Chưa có bằng chứng") and "phân biệt được IC" in verdict(noisy)
    strong = {"ic": {"pairs": 9, "mean": 0.3, "sd": 0.2, "t": 4.5, "positive_share": 1}, "power": {}}
    assert "cần thêm phiên" in verdict(strong)
    write_evidence(forward_check(rows()), tmp_path)
    text = (tmp_path / "KIEM_TRA_PHIEN_KE_TIEP.md").read_text(encoding="utf-8")
    assert "Lợi suất mua được" in text and "+1,000" in text and "Điều chỉnh quyền" in text and "ngoài mẫu" not in text
    assert len(pd.read_csv(tmp_path / "kiem_tra_phien_ke_tiep.csv")) == 3


def test_unranked_rows_and_index_rows_are_excluded():
    frame = rows()
    frame.loc[frame["symbol"].isin(["S00", "S01"]), "foreignBuyValue"] = None  # missing foreign -> unranked
    part = forward_check(frame)["weights"]["balanced"]
    assert all(p["ranked"] == 10 for p in part["pairs"])
    assert part["ic"]["mean"] == pytest.approx(1)
