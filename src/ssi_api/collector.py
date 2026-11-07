"""First read-only SSI diagnostic. DailyStockPrice alone cannot score four intraday factors."""
import uuid
from src.data.store import EventStore, now, TZ
from src.ssi_api.rest import SSIClient

DAILY_MAP={"Openprice":"openPrice","Closeprice":"closePrice","Refprice":"refPrice",
    "Highestprice":"highPrice","Lowestprice":"lowPrice","Totalmatchvol":"totalTradingVolume",
    "Totalmatchval":"totalTradingValue","Foreignbuyvaltotal":"foreignBuyValue",
    "Toreignsellvaltotal":"foreignSellValue","Foreignsellvaltotal":"foreignSellValue"}


def canonical_daily(row):
    result={"symbol":row.get("Symbol"),"tradingDate":row.get("Tradingdate")}
    for key,target in DAILY_MAP.items():
        if key in row:
            if target in result and result[target]!=row[key]:
                raise ValueError("Các tên trường SSI tương đương có giá trị mâu thuẫn.")
            result[target]=row[key]
    return result


def collect_rest(settings):
    client=SSIClient(settings)
    store=None
    try:
        client.authenticate()
        members=[m for index in ("VN30",) for m in client.components(index)]
        symbols={m["symbol"] for m in members}
        if len(symbols)!=len(members):
            raise ValueError("Danh sách thành phần có mã trùng; cần kiểm tra dữ liệu SSI.")
        from datetime import datetime
        day=datetime.now(TZ).strftime("%d/%m/%Y")
        rows=[row for market in ("HOSE",) for row in client.list_all(
            "DailyStockPrice",market=market,fromDate=day,toDate=day) if row.get("Symbol") in symbols]
        if len({r["Symbol"] for r in rows})!=len(rows):
            raise ValueError("SSI trả nhiều snapshot ngày cho cùng mã; cần đối chiếu.")
        store=EventStore(settings.database)
        run="ssi-"+uuid.uuid4().hex
        at=now()
        store.append("ssi",run,at,"connection",{"state":"connecting","update_mode":"snapshot","profile":settings.profile})
        store.append("ssi",run,at,"universe",{"indices":["VN30"],"members":members})
        for row in rows:
            store.append("ssi",run,at,"ssiRaw",{"endpoint":"DailyStockPrice","data":row})
            store.append("ssi",run,at,"stockInfo",canonical_daily(row))
        store.append("ssi",run,now(),"connection",{"state":"snapshot_complete"})
        return {"source":"ssi","run":run,"groups":["VN30"],"members":len(members),"daily_rows":len(rows),
            "four_factor_ready":False,"note":"Chưa có sổ lệnh và phiên intraday; không dùng dữ liệu ngày thay thế."}
    finally:
        client.close()
        if store:
            store.close()
