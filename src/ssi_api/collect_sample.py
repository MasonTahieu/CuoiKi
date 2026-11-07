"""Task 2 offline scenario and review files. Does not read credentials or open sockets."""
from copy import deepcopy
import json
from pathlib import Path
from src.config import PROJECT_ROOT
from src.data.store import EventStore
from src.ssi_api.fake_stream import FakeClock, FakeFactory
from src.ssi_api.stream_collector import Frame, StreamDisconnected, collect_stream


def scenario():
    members=[{"symbol":"DEMO01","index_group":"VN30","marketCode":"HOSE"},
             {"symbol":"HNDEMO01","index_group":"HNX30","marketCode":"HNX"}]
    def message(kind,symbol,second,received,**fields):
        content={"Symbol":symbol,"Exchange":"HNX" if symbol.startswith("HN") else "HOSE",
            "TradingDate":"04/11/2026","Time":f"10:00:{second:02d}",**fields}
        return Frame({"DataType":kind,"Content":content},f"2026-11-04T10:00:{received:02d}+07:00")
    def snapshot(symbol,second,received):
        book={f"{side}{field}{i}": (20000+(-1 if side=="Bid" else 1)*i*50 if field=="Price" else 1000*i)
            for side in ("Bid","Ask") for field in ("Price","Vol") for i in (1,2,3)}
        return message("X",symbol,second,received,Open=19900,LastPrice=20000+second*10,LastVol=100,
            TotalVal=2000000000+second*100000,TotalVol=100000+second*100,TradingSession="LO",TradingStatus="N",**book)
    def room(symbol,second,received):
        return message("R",symbol,second,received,BuyVal=40000000+second*10000,SellVal=20000000,
                       BuyVol=2000+second,SellVol=1000)
    quote=message("X-QUOTE","DEMO01",2,3,BidVol1=None,BidPrice1=19975)
    duplicate=Frame(deepcopy(quote.raw),"2026-11-04T10:00:04+07:00")
    late=message("X-TRADE","DEMO01",0,2,LastPrice=1,LastVol=1,TotalVol=1,TotalVal=1)
    # Source time explicitly earlier than baseline; collector must not overwrite any field.
    late.raw["Content"]["Time"]="09:59:59"
    first=[snapshot("DEMO01",0,1),room("DEMO01",0,1),snapshot("HNDEMO01",0,1),room("HNDEMO01",0,1),
        late,quote,duplicate,message("X-TRADE","OUTSIDE",4,5,LastPrice=1),
        Frame("not valid JSON", "2026-11-04T10:00:06+07:00"),StreamDisconnected()]
    second=[message("X-TRADE","DEMO01",8,9,LastPrice=20100),snapshot("DEMO01",9,10),room("DEMO01",10,11),
        snapshot("HNDEMO01",11,12),room("HNDEMO01",12,13),message("F","HNDEMO01",13,14,TradingStatus="H")]
    return members,[first,second]


def main():
    clock=FakeClock()
    members,scripts=scenario()
    factory=FakeFactory(members,scripts,clock)
    output=PROJECT_ROOT/"evidence"/"task2"
    output.mkdir(parents=True,exist_ok=True)
    database=PROJECT_ROOT/"runtime"/"task2-synthetic.sqlite"
    store=EventStore(database)
    journal=[]
    def sink(**event):
        store.append(**event)
        journal.append(deepcopy(event))
    try:
        report=collect_stream(factory,sink,seconds=30,max_messages=15,
            clock=clock.monotonic,sleep=clock.sleep,wall_now=clock.wall_now)
    finally:store.close()
    (output/"collector_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    (output/"journal.json").write_text(json.dumps(journal,ensure_ascii=False,indent=2),encoding="utf-8")
    lines=["# Task 2 — Collector với luồng SSI giả lập", "", "**DỮ LIỆU GIẢ LẬP**. Hai mã hư cấu, không phải dữ liệu SSI thật.", "",
        f"Kết quả: {report['counters']['received']} thông điệp nhận, {report['counters']['merged']} lần ghép trạng thái, "
        f"{report['counters']['reconnects']} lần kết nối lại, {report['counters']['duplicate']} thông điệp trùng, "
        f"{report['counters']['decode_errors']} lỗi JSON.", "", "## Diễn biến để bạn kiểm tra", "",
        "| Lần kết nối | Thời gian nhận | Loại | Mã | Giá khớp | Ngoại mua | Trường đã đủ? | Trạng thái |", "|---|---|---|---|---|---|---|---|"]
    for event in journal:
        if event["channel"]!="ssiMerged":continue
        state=event["payload"]
        payload=state["payload"]
        kinds=state["field_message_type"]
        changed=state["changed_fields"]
        kind=kinds[changed[0]]
        lines.append(f"| {state['connection_epoch']} | {event['received_at'][11:19]} | {kind} | {state['symbol']} | "
            f"{payload.get('closePrice','—')} | {payload.get('foreignBuyValue','—')} | {state['fields_complete']} | {payload.get('tradingStatus','chưa có')} |")
    lines += ["", "## Các điểm cần kiểm tra", "",
        "1. Ban đầu X chưa đủ trường ngoại; sau R thì fields_complete=True.",
        "2. Quote chỉ cập nhật bid: thời gian trường ngoại giữ nguyên; bidVol1=null làm fields_complete=False.",
        "3. Thông điệp cũ có LastPrice=1 không ghi đè giá mới; thông điệp ngoài nhóm và JSON lỗi không vào trạng thái.",
        "4. Có disconnected rồi connecting/connected lần 2. Các kênh được đăng ký lại, danh sách nhóm lấy lại.",
        "5. Bản ghi đầu của lần kết nối 2 chỉ có giá khớp, chưa có ngoại và fields_complete=False: không dùng dữ liệu trước ngắt.",
        "6. Khi X và R mới đến, trạng thái mới đủ trường. HNX bị HALT chỉ ảnh hưởng HNDEMO01; DEMO01 vẫn NORMAL.",
        "", "fields_complete chỉ kiểm tra có trường và khác null, không phải đủ điều kiện xếp hạng. ranking_ready luôn False ở task 2.",
        "", "## Kết quả đã lưu", "",
        "- collector_report.json: kết quả và trạng thái cuối.",
        "- journal.json: chuỗi sự kiện trong kịch bản, có source=synthetic, run và connection_epoch.",
        "- runtime/task2-synthetic.sqlite: dữ liệu của các lần chạy, mỗi lần có run riêng.",
        "", "Lệnh tạo lại: python -X utf8 -m src.ssi_api.collect_sample. Không cần API/SDK hoặc kết nối mạng.",
        "", "Có thể phát lại và kiểm tra chất lượng nhật ký này bằng công cụ task 3. [Kết quả mẫu task 3](../task3/KET_QUA_MAU.md)"]
    (output/"KET_QUA_MAU.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({"source":"synthetic","network_called":False,"run":report["run"],
        "counters":report["counters"],"review":str(output/"KET_QUA_MAU.md")},ensure_ascii=False,indent=2))


if __name__=="__main__":main()
