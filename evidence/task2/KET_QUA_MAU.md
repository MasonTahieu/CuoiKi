# Task 2 — Collector với luồng SSI giả lập

**DỮ LIỆU GIẢ LẬP**. Hai mã hư cấu, không phải dữ liệu SSI thật.

Kết quả: 15 thông điệp nhận, 11 lần ghép trạng thái, 1 lần kết nối lại, 1 thông điệp trùng, 1 lỗi JSON.

## Diễn biến để bạn kiểm tra

| Lần kết nối | Thời gian nhận | Loại | Mã | Giá khớp | Ngoại mua | Trường đã đủ? | Trạng thái |
|---|---|---|---|---|---|---|---|
| 1 | 10:00:01 | X | DEMO01 | 20000.0 | — | False | NORMAL |
| 1 | 10:00:01 | R | DEMO01 | 20000.0 | 40000000.0 | True | NORMAL |
| 1 | 10:00:01 | X | HNDEMO01 | 20000.0 | — | False | NORMAL |
| 1 | 10:00:01 | R | HNDEMO01 | 20000.0 | 40000000.0 | True | NORMAL |
| 1 | 10:00:03 | X-QUOTE | DEMO01 | 20000.0 | 40000000.0 | False | NORMAL |
| 2 | 10:00:09 | X-TRADE | DEMO01 | 20100.0 | — | False | chưa có |
| 2 | 10:00:10 | X | DEMO01 | 20090.0 | — | False | NORMAL |
| 2 | 10:00:11 | R | DEMO01 | 20090.0 | 40100000.0 | True | NORMAL |
| 2 | 10:00:12 | X | HNDEMO01 | 20110.0 | — | False | NORMAL |
| 2 | 10:00:13 | R | HNDEMO01 | 20110.0 | 40120000.0 | True | NORMAL |
| 2 | 10:00:14 | F | HNDEMO01 | 20110.0 | 40120000.0 | True | HALT |

## Các điểm cần kiểm tra

1. Ban đầu X chưa đủ trường ngoại; sau R thì fields_complete=True.
2. Quote chỉ cập nhật bid: thời gian trường ngoại giữ nguyên; bidVol1=null làm fields_complete=False.
3. Thông điệp cũ có LastPrice=1 không ghi đè giá mới; thông điệp ngoài nhóm và JSON lỗi không vào trạng thái.
4. Có disconnected rồi connecting/connected lần 2. Các kênh được đăng ký lại, danh sách nhóm lấy lại.
5. Bản ghi đầu của lần kết nối 2 chỉ có giá khớp, chưa có ngoại và fields_complete=False: không dùng dữ liệu trước ngắt.
6. Khi X và R mới đến, trạng thái mới đủ trường. HNX bị HALT chỉ ảnh hưởng HNDEMO01; DEMO01 vẫn NORMAL.

fields_complete chỉ kiểm tra có trường và khác null, không phải đủ điều kiện xếp hạng. ranking_ready luôn False ở task 2.

## Kết quả đã lưu

- collector_report.json: kết quả và trạng thái cuối.
- journal.json: chuỗi sự kiện trong kịch bản, có source=synthetic, run và connection_epoch.
- runtime/task2-synthetic.sqlite: dữ liệu của các lần chạy, mỗi lần có run riêng.

Lệnh tạo lại: python -X utf8 -m src.ssi_api.collect_sample. Không cần API/SDK hoặc kết nối mạng.

Có thể phát lại và kiểm tra chất lượng nhật ký này bằng công cụ task 3. [Kết quả mẫu task 3](../task3/KET_QUA_MAU.md)
