# Thu stream VN30 chiều 09/11/2026 và đối chiếu với REST

Run `ssi-stream-c7ce23412cf54938860e9c08095461eb`, từ 13:34 đến 15:05, đăng nhập không OTP. Nhật ký SQLite 1,2 GB nằm ở `runtime/` trên máy và không đưa lên GitHub. Số liệu chỉ từ một buổi chiều, chưa có phiên sáng và ATO.

## Tổng quan

| Chỉ số | Kết quả |
|---|---|
| Gói nhận | 144.055 (QUOTE 89.371, TRADE 52.049, ROOM 2.625, MARKET_FLAG 10) |
| Lỗi giải mã, gói bị từ chối | 0 |
| Gói trùng | 7.633 (5,3%) |
| Số lần nối lại | 6 |

## Đối chiếu tổng cuối ngày với `securitiesSummary`

Tệp [doi_chieu_stream_rest.csv](doi_chieu_stream_rest.csv) có đủ 30 mã.

| Trường | Số mã so được | Tỷ lệ stream/REST thấp nhất | Tỷ lệ cao nhất |
|---|---|---|---|
| Khối lượng khớp | 30 | 1,0000000 | 1,0000000 |
| Giá trị khớp (`a × v`, suy ra) | 30 | 0,9999999 | 1,0000002 |
| Giá trị mua của khối ngoại | 29 | 1,0000000 | 1,0000000 |
| Giá trị bán của khối ngoại | 30 | 1,0000000 | 1,0000000 |
| Giá mở cửa | 30 | 1,0000000 | 1,0000000 |

GVR không tính được tỷ lệ mua của khối ngoại vì cả hai nguồn đều bằng 0. Kết quả này cho thấy hai nguồn dùng cùng đơn vị và cùng định nghĩa tổng cuối ngày. Nó chưa trả lời số khối ngoại có gồm giao dịch thỏa thuận hay không.

## Nhịp và độ trễ

Độ trễ là thời điểm nhận trừ thời gian `t` của nguồn. Giá trị âm nghĩa là nguồn đi trước đồng hồ máy.

| Giai đoạn, loại gói | Số gói | Độ trễ trung vị (giây) | Độ trễ cao nhất (giây) | Khoảng cách trung vị giữa hai gói của một mã (giây) |
|---|---|---|---|---|
| Khớp lệnh liên tục, QUOTE | 83.408 | 0,34 | 1,65 | 0,5 |
| Khớp lệnh liên tục, TRADE | 47.749 | −0,14 | 0,80 | 0,1 |
| Khớp lệnh liên tục, ROOM | 1.670 | 20,35 | 29,93 | 60,0 |
| ATC, QUOTE | 5.933 | 0,47 | 2,93 | 1,6 |
| ATC, ROOM | 378 | 20,72 | 29,98 | 60,0 |
| 14:45–15:00, TRADE | 4.300 | 13,18 | 18,76 | 0,0 |
| 14:45–15:00, ROOM | 425 | 20,97 | 30,49 | 60,0 |

- Gói ROOM có `t` luôn ở giây 00. Tuổi dữ liệu ngay trước đợt kế tiếp có phân vị 99 là 89,7 giây, và cao nhất 131,5 giây khi lỡ một đợt lúc nối lại.
- Không có gói TRADE nào trong lúc ATC. Kết quả khớp ATC đến thành một đợt sau 14:45.
- Mã im lâu nhất trong lúc khớp lệnh liên tục: VIB 100 giây, LPB 91 giây, STB 85 giây.

## Cờ phiên

`MARKET_FLAG` báo `ATC` lúc 14:30:00 và `C` lúc khoảng 14:45:02 cho HOSE. Không có cờ `PT`, khác với lịch trong `src/data/ssi_quality.py`. Không có cờ `LO` vì lần chạy bắt đầu giữa phiên.

## Số mã dùng được khi phát lại

| Mốc | Ngưỡng 60/10 giây | Ngưỡng 90/30 giây |
|---|---|---|
| 13:40:30 | 8/30 | 30/30 |
| 14:00:30 | 8/30 | 30/30 |
| 14:15:30 | 7/30 | 30/30 |
| 14:28:30 | 7/30 | 30/30 |

Ngưỡng 60/10 chặn vì độ trễ của gói khối ngoại, không phải vì giá hay sổ lệnh. Trong ATC và sau 14:45, 0/30 mã dùng được ở cả hai ngưỡng, đúng chủ đích vì mô hình chỉ xếp hạng trong lúc khớp lệnh liên tục.

Quanh lần đổi token lúc 13:48:05, với ngưỡng thử 100/35 giây:

| Mốc | Số mã dùng được | Lý do |
|---|---|---|
| 13:47:50 | 30/30 | |
| 13:48:15 | 9/30 | Thiếu trường, chủ yếu khối ngoại |
| 13:48:45 | 26/30 | Thiếu trường khối ngoại |
| 13:49:15 | 30/30 | |

## Hai lỗi phát hiện được, đã sửa cùng ngày

1. **Bộ thu xử lý sai lúc đổi token.** Token SSI sống 15 phút (đo được 899 giây) và SDK đóng rồi mở lại kết nối trước hạn 60 giây. `collect_stream` coi đó là mất kết nối, và thời gian chờ `2^n` giây không được đặt lại. Quan sát được 1, 2, 4, 8, 17, 32 giây. Lần nối thứ 11 của một khung 2,5 giờ sẽ chờ khoảng 17 phút.
2. **`securitiesByBoard?index=VN30` có lúc chỉ trả một dòng là chính chỉ số.** Lúc 14:58:41 trả 30 mã, lúc 15:49–15:50 trả đúng một dòng `VN30` ở mọi lần gọi; chưa rõ quy luật. Mô phỏng offline trên bản sao dữ liệu cho thấy `history` không báo lỗi, ghi 15 dòng rác và trang web hiện phiên mới với 1 mã, 0 mã xếp hạng.

Sau khi sửa, chạy lại với SSI thật lúc 16:03 trên bản sao dữ liệu: SSI vẫn trả một dòng, `history` dùng thành phần phiên 06/11 kèm cảnh báo, phiên 09/11 có đủ 30 mã và 30 mã được xếp hạng, không có dòng rác. Phát lại mốc 14:28:30 với ngưỡng mới cho 30/30 mã dùng được.
