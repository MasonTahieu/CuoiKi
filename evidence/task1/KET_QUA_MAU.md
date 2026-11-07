# Task 1 — Kết quả giải mã mẫu

**DỮ LIỆU GIẢ LẬP**: sáu thông điệp tự tạo, không phải dữ liệu SSI thật.

| Loại | Mã hư cấu | Thời gian nguồn | Trường sau giải mã | Ghi nhận |
|---|---|---|---|---|
| F | DEMO01 | 2026-11-04T10:00:00+07:00 | tradingSession=LO, tradingStatus=NORMAL | Không có lỗi trường trong mẫu |
| X-QUOTE | DEMO01 | 2026-11-04T10:00:00+07:00 | bidPrice1=20000.0, bidPrice2=19950.0, bidPrice3=19900.0, bidVol1=1000.0, bidVol2=2000.0, bidVol3=3000.0, askPrice1=20050.0, askPrice2=20100.0, askPrice3=20150.0, askVol1=1200.0, askVol2=2200.0, askVol3=3200.0 | Không có lỗi trường trong mẫu |
| X-TRADE | DEMO01 | 2026-11-04T10:00:00+07:00 | refPrice=19900.0, closePrice=20050.0, lastTradeVolume=100.0, totalTradingVolume=100000.0, totalTradingValue=2000000000.0 | Không có lỗi trường trong mẫu |
| R | DEMO01 | 2026-11-04T10:00:00+07:00 | foreignBuyVolume=2000.0, foreignSellVolume=1000.0, foreignBuyValue=40100000.0, foreignSellValue=20050000.0 | FOREIGN_VALUE_ESTIMATED |
| B | DEMO01 | 2026-11-04T10:00:00+07:00 | openPrice=19900.0, highPrice=20100.0, lowPrice=19800.0, closePrice=20050.0, lastTradeVolume=100.0 | B_VALUE_NOT_CUMULATIVE |
| X | HNDEMO01 | 2026-11-04T10:00:00+07:00 | tradingSession=ATC, tradingStatus=NORMAL, openPrice=14800.0, closePrice=15000.0, totalTradingVolume=100000.0, totalTradingValue=1500000000.0, ohlcClosePrice=14900.0, bidPrice1=ATC, askPrice1=ATC | Không có lỗi trường trong mẫu |

## Bạn kiểm tra những gì?

1. X-TRADE: lastTradeVolume=100, totalTradingVolume=100000; không bị nhập nhằng.
2. R: ngoại mua/bán được chuyển thành số và có FOREIGN_VALUE_ESTIMATED cho HOSE.
3. X-QUOTE: chỉ ba mức đầu, không có mức 4 trong kết quả.
4. F: N → NORMAL, giữ phiên LO. X cuối giữ ATC, không đổi sang LO.
5. B: Volume là lastTradeVolume; Value=0 không thành totalTradingValue=0.
6. X cuối: LastPrice=15000 thành closePrice; Close=14900 giữ riêng ở ohlcClosePrice.

Chưa ghép sáu bản ghi thành trạng thái cổ phiếu, chưa có kết nối/collector, chưa chấm điểm. Đó là các task sau.
