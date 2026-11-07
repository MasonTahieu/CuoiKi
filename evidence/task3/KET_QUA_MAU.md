# Task 3 — Kết quả lưu trữ, phát lại và chất lượng dữ liệu

**Hoàn toàn giả lập (`source=synthetic`), không gọi mạng và không dùng khóa SSI/NEO.**

Hai mã hư cấu DEMO01 và HNDEMO01 minh họa hai nhóm; không phải thành phần VN30/HNX30 thật.
`data_usable` là kết quả kiểm tra dữ liệu tại mốc chọn. Báo cáo replay dùng `ranking_ready=false`.

## 1. Kiểm tra theo mốc

| Tình huống | Mốc giờ +07:00 | Trạng thái ghi nhận | VN30 dùng được | HNX30 dùng được |
|---|---|---|---|---|
| Dữ liệu ban đầu | 10:00:01+07:00 | connected | 1/1 | 1/1 |
| Một trường bid bị null | 10:00:03+07:00 | connected | 0/1 | 1/1 |
| Đang mất kết nối | 10:00:06.500000+07:00 | disconnected | 0/1 | 0/1 |
| Mới kết nối lại, chỉ nhận Trade | 10:00:09+07:00 | connected | 0/1 | 0/1 |
| Đã nhận lại X+R của hai mã | 10:00:13+07:00 | connected | 1/1 | 1/1 |
| HNX tạm ngừng giao dịch, trước khi collector dừng | 10:00:14+07:00 | connected | 1/1 | 0/1 |
| Collector đã dừng | 10:00:14+07:00 | stopped | 0/1 | 0/1 |
| Luồng vẫn có quote, khối ngoại đã quá 60 giây | 10:01:03+07:00 | connected | 0/1 | 0/1 |

Độ phủ được tính trên danh sách bootstrap của run này (mỗi nhóm chỉ 1 mã), không phải độ phủ 30 mã thực tế.
Các mốc phát lại không lấy giá/trường xuất hiện sau mốc chọn. Bản ghi `ssiMerged` chỉ để đối chiếu, không quyết định trạng thái replay.

## 2. Những kết quả cần kiểm tra

- 10:00:01: giá DEMO01 là **20.000**, chưa dùng giá ở các mốc sau.
- 10:00:03: `bidVol1=null` làm DEMO01 thiếu trường; mã HNX vẫn đủ dữ liệu.
- 10:00:06,5: mất kết nối; dữ liệu nền cũ bị xóa. Gap đang mở được ghi nhận 0,5 giây tại mốc này.
- 10:00:09: đã kết nối lại nhưng chỉ có giá Trade; vẫn thiếu mở cửa, sổ lệnh và khối ngoại.
- 10:00:13: cả hai mã qua kiểm tra dữ liệu; gap hoàn tất dài **1 giây**. Cờ ngoại ước tính của mã HOSE vẫn được giữ.
- 10:00:14, ngay sau F: HNX bị HALT; VN30 vẫn qua kiểm tra. Dùng event ID để phân biệt với sự kiện dừng cùng giây.
- Sau sự kiện dừng: vẫn xem được snapshot lịch sử, nhưng dữ liệu bị chặn vì kết nối đã dừng.

## 3. Trường mới không làm mới các trường khác

Run thứ hai giữ luồng hoạt động bằng các quote cách nhau tối đa 13 giây. Tại 10:01:03:

| Mã | Tuổi giá bid 1 | Tuổi khối ngoại mua | Chênh nguồn–nhận của bid 1 | Lý do chặn |
|---|---|---|---|---|
| DEMO01 | 1 giây | 63 giây | 1 giây | Trường quá cũ |
| HNDEMO01 | 1 giây | 63 giây | 1 giây | Trường quá cũ |

Ngưỡng mặc định: trường động tối đa 60 giây; chênh nguồn–nhận tối đa 10 giây. Đây là quy ước thử nghiệm, chưa phải SLA của SSI.
Chênh thời gian ghi nhận có thể bao gồm lệch đồng hồ; không thể coi đó là phép đo độ trễ mạng thuần túy.

## 4. Tệp để xem

- [Báo cáo chất lượng lúc 10:00:13](export/quality.json)
- [Snapshot CSV](export/snapshot.csv) · [Chất lượng từng trường](export/field_quality.csv) · [Gap](export/gaps.csv)
- [Báo cáo dữ liệu cũ](stale-export/quality.json)
- [Toàn bộ mốc kiểm tra](checkpoints.json)
- [Hướng dẫn task 3](../../docs/TASK_3_LUU_TRU_REPLAY_CHAT_LUONG.md)

Mỗi thư mục xuất có manifest SHA-256 để đối chiếu nội dung; đây không phải chữ ký xác nhận của SSI.
Kho SQLite và các tệp mẫu được tạo lại bằng `python -X utf8 -m src.ssi_api.replay_sample`.
Mỗi lần chạy thêm run riêng; không ghi đè hoặc trộn dữ liệu thật.

Phần kiểm chứng công thức và xếp hạng giả lập có bảng mẫu riêng. [Kết quả mẫu task 4](../task4/KET_QUA_MAU.md)
