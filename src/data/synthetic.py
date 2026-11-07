"""Deterministic market-shaped fixtures; imaginary symbols, never a NEO sample."""
from datetime import datetime, timedelta
from src.data.store import TZ


def demo_events():
    start = datetime(2026, 10, 26, 9, 30, tzinfo=TZ)
    events = []
    def add(at, channel, payload):
        events.append(dict(source="synthetic", run="synthetic-v1", received_at=at.isoformat(), channel=channel, payload=payload))
    members = [dict(symbol=f"DEMO{i:02d}", stockName=f"Công ty giả lập {i}",
        stockType="ST", marketCode="HOSE", tradingDate="26/10/2026", tradingStatus="NORMAL") for i in range(1,13)]
    add(start, "universe", {"index":"SYNTHETIC_12_NOT_VN30", "members":members})
    add(start, "marketSession", {"marketCode":"HOSE", "marketStatus":"LO"})
    for step in range(3):
        at = start + timedelta(minutes=5*step)
        for i, member in enumerate(members, 1):
            opening = 18000 + i*2000
            price = opening + (i-6)*100 + step*(i%4-1)*50
            quote = dict(member, openPrice=opening, closePrice=price, refPrice=opening-100,
                highPrice=max(opening,price)+100, lowPrice=min(opening,price)-100,
                totalTradingVolume=(i+step+1)*100000,
                totalTradingValue=(i+step+1)*100000*price,
                foreignBuyValue=i*70000000+step*10000000,
                foreignSellValue=(13-i)*40000000+step*5000000)
            for level in (1,2,3):
                quote[f"bidPrice{level}"] = str(price-level*50)
                quote[f"askPrice{level}"] = str(price+level*50)
                quote[f"bidVol{level}"] = (i+level)*1000
                quote[f"askVol{level}"] = (14-i+level)*1000
            add(at, "stockInfo", quote)
    return events


def demo_groups():
    """Demo board in the SSI shape: one VN30 group of fictional DEMO tickers."""
    from copy import deepcopy
    base=demo_events()
    members=[dict(m,index_group="VN30") for m in base[0]["payload"]["members"]]
    events=[dict(base[0],run="synthetic-vn30-v1",payload={"indices":["VN30"],"members":members})]
    for event in base[1:]:
        copy=deepcopy(event)
        copy["run"]="synthetic-vn30-v1"
        events.append(copy)
    return events
