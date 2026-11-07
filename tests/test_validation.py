"""Out-of-sample check (src.analytics.validation). Offline, synthetic daily rows."""
import pandas as pd
import pytest

from src.analytics.validation import forward_check, verdict, write_evidence


def rows(days=4, size=12, forward=lambda i, d: 0.0):
    out = []
    for d in range(days):
        for i in range(size):
            out.append({"symbol": f"S{i:02d}", "index_group": "VN30", "tradingDate": f"2026-11-0{d + 1}",
                        # higher i -> higher momentum, turnover and foreign ratio -> higher score
                        "openPrice": 10_000, "closePrice": 10_000 + 20 * i, "totalTradingValue": 1e9 * (i + 1),
                        "foreignBuyValue": 1e7 * i, "foreignSellValue": 1e7,
                        "priceChangePercent": forward(i, d)})
    out.append({"symbol": "VN30", "index_group": "INDEX", "tradingDate": "2026-11-01", "closePrice": 1800.0})
    return pd.DataFrame(out)


def test_perfect_ordering_gives_ic_one_and_positive_spread():
    result = forward_check(rows(forward=lambda i, d: 0.1 * i))
    part = result["weights"]["balanced"]
    assert result["sessions"] == 4 and result["pairs"] == 3
    assert [p["ic"] for p in part["pairs"]] == pytest.approx([1, 1, 1])
    assert part["ic"]["mean"] == pytest.approx(1) and part["ic"]["positive_share"] == 1
    assert part["top_minus_bottom_pp"]["mean"] == pytest.approx(0.1 * 7)  # mean(7..11) - mean(0..4)
    assert all(p["ranked"] == 12 for p in part["pairs"])


def test_reversed_ordering_is_reported_as_negative_not_hidden():
    part = forward_check(rows(forward=lambda i, d: -0.1 * i))["weights"]["momentum"]
    assert part["ic"]["mean"] == pytest.approx(-1)


def test_forward_return_comes_from_the_next_session_only():
    # Day-t returns are a perfect match for day-t scores, the next day is the reverse: a look-ahead
    # bug (using same-day returns) would report IC = +1, the correct check reports -1.
    result = forward_check(rows(days=2, forward=lambda i, d: 0.1 * i if d == 0 else -0.1 * i))
    assert result["weights"]["balanced"]["pairs"][0]["ic"] == pytest.approx(-1)


def test_flat_returns_leave_ic_undefined_and_verdict_is_honest(tmp_path):
    result = forward_check(rows(forward=lambda i, d: 0.0))
    part = result["weights"]["balanced"]
    assert part["ic"]["pairs"] == 0 and verdict(part) == "Chưa đủ phiên để kiểm chứng."
    noisy = forward_check(rows(days=6, forward=lambda i, d: ((i * 7 + d * 3) % 5) - 2.0))["weights"]["balanced"]
    assert "Không có bằng chứng" in verdict(noisy) or "liên hệ" in verdict(noisy)
    write_evidence(forward_check(rows(forward=lambda i, d: 0.1 * i)), tmp_path)
    text = (tmp_path / "KIEM_CHUNG_NGOAI_MAU.md").read_text(encoding="utf-8")
    assert "IC trung bình" in text and "+1,000" in text
    assert len(pd.read_csv(tmp_path / "kiem_chung_ngoai_mau.csv")) == 3


def test_unranked_rows_and_index_rows_are_excluded():
    frame = rows(forward=lambda i, d: 0.1 * i)
    frame.loc[frame["symbol"].isin(["S00", "S01"]), "foreignBuyValue"] = None  # missing foreign -> unranked
    part = forward_check(frame)["weights"]["balanced"]
    assert all(p["ranked"] == 10 for p in part["pairs"])
    assert part["ic"]["mean"] == pytest.approx(1)
