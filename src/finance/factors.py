"""Raw, interpretable intraday factors. This is not a return forecast."""
import math
from numbers import Real

FOREIGN_FIELDS = {
    "value": ("foreignBuyValue", "foreignSellValue", "totalTradingValue", "foreign_net_vnd"),
    "volume": ("foreignBuyVolume", "foreignSellVolume", "totalTradingVolume", "foreign_net_volume"),
}


def factors(row, *, foreign_basis="value"):
    if foreign_basis not in FOREIGN_FIELDS:
        raise ValueError("Chọn yếu tố ngoại theo value hoặc volume.")
    p, opening, turnover = row["closePrice"], row["openPrice"], row["totalTradingValue"]
    if min(p, opening, turnover) <= 0:
        raise ValueError("giá/giá mở cửa/giá trị giao dịch phải > 0")
    bids = [row[f"bidPrice{i}"] for i in (1,2,3)]
    asks = [row[f"askPrice{i}"] for i in (1,2,3)]
    bq = [row[f"bidVol{i}"] for i in (1,2,3)]
    aq = [row[f"askVol{i}"] for i in (1,2,3)]
    if min(bids + asks) <= 0 or min(bq + aq) < 0:
        raise ValueError("giá/khối lượng sổ lệnh không hợp lệ")
    if bids != sorted(bids, reverse=True) or asks != sorted(asks) or bids[0] > asks[0]:
        raise ValueError("sổ lệnh chéo hoặc sai thứ tự giá")
    quantity = sum(bq + aq)
    if quantity <= 0:
        raise ValueError("không có độ sâu ba mức giá")
    buy_field, sell_field, total_field, net_field = FOREIGN_FIELDS[foreign_basis]
    inputs = []
    for field in (buy_field, sell_field, total_field):
        value = row.get(field)
        if not isinstance(value, Real) or isinstance(value, bool) or not math.isfinite(value) or value < 0:
            raise ValueError(f"thiếu/sai dữ liệu khối ngoại ({foreign_basis}): {field}")
        inputs.append(float(value))
    buy, sell, total = inputs
    if total <= 0:
        raise ValueError(f"mẫu số khối ngoại ({foreign_basis}) phải > 0: {total_field}")
    foreign_net = buy - sell
    ratio = foreign_net / total
    if abs(ratio) > 1:
        raise ValueError("tỷ lệ ngoại vượt phạm vi; cần kiểm tra đơn vị/phạm vi giao dịch")
    result = dict(momentum=100 * (p / opening - 1), turnover=turnover,
        spread_bps=10000 * (asks[0]-bids[0]) / ((asks[0]+bids[0])/2),
        depth_vnd=sum(p*q for p,q in zip(bids+asks, bq+aq)),
        foreign_ratio=ratio,
        imbalance=(sum(bq)-sum(aq))/quantity)
    result[net_field] = foreign_net
    if not all(math.isfinite(v) for v in result.values()):
        raise ValueError("yếu tố không hữu hạn")
    return result
