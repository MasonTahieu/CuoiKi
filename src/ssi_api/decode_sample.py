"""Task 1 review artifact. Fabricated SSI-shaped messages, no live connectivity."""
import json
from src.config import PROJECT_ROOT
from src.ssi_api.decoder import decode_fcdata


def sample_messages():
    common={"Symbol":"DEMO01","Exchange":"HOSE","TradingDate":"04/11/2026","Time":"10:00:00"}
    return [
        {"DataType":"F","Content":{**common,"RType":"F","TradingSession":"LO","TradingStatus":"N"}},
        {"DataType":"X-QUOTE","Content":json.dumps({**common,"BidPrice1":"20000","BidVol1":1000,
            "BidPrice2":19950,"BidVol2":2000,"BidPrice3":19900,"BidVol3":3000,
            "AskPrice1":20050,"AskVol1":1200,"AskPrice2":20100,"AskVol2":2200,
            "AskPrice3":20150,"AskVol3":3200,"AskPrice4":20200,"AskVol4":4000})},
        {"DataType":"X-TRADE","Content":{**common,"LastPrice":20050,"LastVol":100,"TotalVol":100000,
            "TotalVal":2000000000,"RefPrice":19900}},
        {"DataType":"R","Content":{**common,"BuyVol":"2000","SellVol":1000,"BuyVal":40100000,"SellVal":20050000}},
        {"DataType":"B","Content":{"RType":"B","Symbol":"DEMO01","Exchange":"HOSE",
            "Time":"2026-11-04T10:00:00+07:00","Open":19900,"High":20100,"Low":19800,
            "Close":20050,"Volume":100,"Value":0}},
        {"DataType":"X","Content":{**common,"Symbol":"HNDEMO01","Exchange":"HNX","MarketId":"HNX",
            "LastPrice":15000,"Close":14900,"Open":14800,"TotalVal":1500000000,"TotalVol":100000,
            "TradingSession":"ATC","TradingStatus":"N","BidPrice1":"ATC","AskPrice1":"ATC"}},
    ]


def main():
    folder=PROJECT_ROOT/"evidence"/"task1"
    folder.mkdir(parents=True,exist_ok=True)
    messages=sample_messages()
    decoded=[decode_fcdata(m,received_at="2026-11-04T10:00:01+07:00",source="synthetic") for m in messages]
    (folder/"ssi_synthetic_input.json").write_text(json.dumps({"source":"synthetic","messages":messages},ensure_ascii=False,indent=2),encoding="utf-8")
    (folder/"ssi_decoded_output.json").write_text(json.dumps(decoded,ensure_ascii=False,indent=2),encoding="utf-8")
    lines=["# Task 1 — Kết quả giải mã mẫu", "", "**DỮ LIỆU GIẢ LẬP**: sáu thông điệp tự tạo, không phải dữ liệu SSI thật.", "",
           "| Loại | Mã hư cấu | Thời gian nguồn | Trường sau giải mã | Ghi nhận |", "|---|---|---|---|---|"]
    for item in decoded:
        fields=", ".join(f"{k}={v}" for k,v in item["payload"].items() if k not in {"symbol","tradingDate","marketCode"})
        codes=", ".join(i["code"] for i in item["issues"]) or "Không có lỗi trường trong mẫu"
        lines.append(f"| {item['message_type']} | {item['payload']['symbol']} | {item['source_at']} | {fields} | {codes} |")
    lines += ["", "## Bạn kiểm tra những gì?", "",
        "1. X-TRADE: lastTradeVolume=100, totalTradingVolume=100000; không bị nhập nhằng.",
        "2. R: ngoại mua/bán được chuyển thành số và có FOREIGN_VALUE_ESTIMATED cho HOSE.",
        "3. X-QUOTE: chỉ ba mức đầu, không có mức 4 trong kết quả.",
        "4. F: N → NORMAL, giữ phiên LO. X cuối giữ ATC, không đổi sang LO.",
        "5. B: Volume là lastTradeVolume; Value=0 không thành totalTradingValue=0.",
        "6. X cuối: LastPrice=15000 thành closePrice; Close=14900 giữ riêng ở ohlcClosePrice.",
        "", "Chưa ghép sáu bản ghi thành trạng thái cổ phiếu, chưa có kết nối/collector, chưa chấm điểm. Đó là các task sau."]
    (folder/"KET_QUA_MAU.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("Đã tạo evidence/task1/KET_QUA_MAU.md và hai tệp JSON giả lập. Không gọi mạng.")


if __name__=="__main__":
    main()
