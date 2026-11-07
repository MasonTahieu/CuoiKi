# Bản nháp bổ sung báo cáo theo nguồn SSI FastConnect V3

Bản nháp này dùng để thay hoặc bổ sung các mục tương ứng của `MSSV_HoTen_BaoCao.pdf` khi đã có dữ liệu thật. Các ô `[ĐIỀN SAU]` chỉ được điền bằng số liệu từ `evidence/v3_smoke`, `evidence/v3_sessions` và `runtime/ssi_daily.sqlite`. Không điền bằng dữ liệu giả lập.

## Căn cứ chọn nguồn (thêm vào Mục 1 và Mục 2)

Đề cuối kỳ bản cập nhật cho phép sinh viên dùng thêm SSI FastConnect API tại developers.ssi.com.vn. Dự án ban đầu dùng NEO API. Đã lấy được token NEO, nhưng yêu cầu đọc dữ liệu thị trường bị trả HTTP 401 với mã `NEOINP000401`. Vì vậy, nguồn dữ liệu cốt lõi của sản phẩm là SSI FastConnect API V3. Nhánh NEO được giữ trong mã nguồn để truy vết.

## Mục 4. Dữ liệu SSI FastConnect V3 (thay Mục 4 hiện tại)

**Kết nối.** Sản phẩm dùng thư viện chính thức `ssi-sdk` 3.3.2. Ứng dụng đăng nhập bằng API Key/Secret, kèm OTP khi mở luồng trực tiếp. REST gửi tới `https://api.ssi.com.vn/api/v3/data/…` và luồng WebSocket tới `wss://stream.ssi.com.vn/ws/v3`. Ứng dụng chỉ gọi dữ liệu thị trường, không gọi route giao dịch hay tài khoản. Máy chủ chỉ giữ một phiên đăng nhập cho mỗi API Key, nên REST và luồng trực tiếp dùng chung một lần đăng nhập.

**Mức sử dụng so với yêu cầu tối thiểu của đề.** Sản phẩm dùng một luồng WebSocket có lưu trữ (ba topic theo rổ cho mỗi nhóm, cộng cờ phiên) và hai nhóm REST: thành phần chỉ số và tổng hợp giao dịch ngày.

| Nhóm | Endpoint / topic | Tần suất | Lưu ở đâu |
|---|---|---|---|
| Thành phần nhóm | `GET data/securitiesByBoard?index=VN30|HNX30` | Mỗi lần kết nối | Sự kiện `universe` trong `runtime/ssi.sqlite` |
| Giao dịch khớp | `trade.VN30@*`, `trade.HNX30@*` | Theo từng lệnh khớp | `ssiRaw`, `ssiDecoded` |
| Sổ lệnh | `quote.VN30@*`, `quote.HNX30@*` | Theo thay đổi sổ lệnh | như trên |
| Khối ngoại | `room.VN30@*`, `room.HNX30@*` | Theo thay đổi | như trên |
| Phiên | `market.flag` | Khi đổi phiên | như trên, trải xuống từng mã |
| Tổng hợp ngày | `GET data/securitiesSummary?index=…&from=…&to=…` | 15:05 mỗi ngày và khi lấy lịch sử | `runtime/ssi_daily.sqlite` |

**Từ điển dữ liệu.** Xem bảng "Dữ liệu dùng từ V3" trong `docs/V3_KET_NOI.md`. Có hai trường suy ra:
- `totalTradingValue = averagePrice × totalTradingVolume`, vì gói `trade` không có tổng giá trị khớp. Trường này được đối chiếu với `totalMatchValue` của REST.
- Phiên của từng mã lấy từ cờ phiên của sàn. Nếu chưa nhận cờ thì suy từ lịch giao dịch và hiển thị cảnh báo.

**Chất lượng dữ liệu.**
- Trường vắng mặt khác trường null: gói tin thiếu số không bị đổi thành 0.
- Gói tin trùng bị bỏ, gói đến muộn không ghi đè giá trị mới hơn.
- Mỗi lần kết nối lại phải chờ dữ liệu nền mới.
- Dữ liệu quá ngưỡng tuổi bị loại khỏi xếp hạng.
- Các trường lũy kế giảm bất thường được đánh dấu.
- Đối chiếu cuối ngày giữa luồng trực tiếp và REST: `[ĐIỀN SAU: trung vị tỷ lệ khối lượng, giá trị, khối ngoại]`.

## Mục 7. Kiểm thử và kết quả (bổ sung phần dữ liệu thật)

| Nội dung | Kết quả |
|---|---|
| Smoke test (ngày, số mã mỗi nhóm, loại gói tin, lỗi giải mã) | `[ĐIỀN SAU]` |
| Số phiên đã thu trong phiên và số phiên lịch sử | `[ĐIỀN SAU: ≥ 5, mục tiêu 10]` |
| Tỷ lệ mốc 15 phút có xếp hạng, theo nhóm | `[ĐIỀN SAU: summary.ranked_share]` |
| Độ ổn định hạng giữa hai mốc liên tiếp (Spearman trung bình, tỷ lệ trùng top 5) | `[ĐIỀN SAU]` |
| Độ nhạy: 25/25/25/25 so với 40/20/20/20; khối ngoại theo giá trị so với theo khối lượng | `[ĐIỀN SAU]` |
| Ngưỡng dữ liệu cũ chọn từ phân vị khoảng cập nhật | `[ĐIỀN SAU: p90/p95 theo cụm và ngưỡng chọn]` |
| Độ bền của thứ hạng yếu tố theo ngày | `[ĐIỀN SAU: evaluate_daily]` |

Cách diễn giải: các số liệu này đo độ đầy đủ và độ ổn định của công cụ sàng lọc. Chúng không phải bằng chứng về khả năng dự báo lợi suất.

## Mục 8. Hạn chế (bổ sung)

- V3 không gửi trạng thái từng mã, nên sản phẩm không tự phát hiện mã bị tạm ngừng giao dịch.
- Lịch giao dịch dùng để suy phiên chưa tính ngày nghỉ lễ.
- Giá trị khớp trong phiên là số suy ra.
- Cần ghi rõ giá trị khối ngoại là số chính xác hay số ước tính, theo kết quả đối chiếu.
