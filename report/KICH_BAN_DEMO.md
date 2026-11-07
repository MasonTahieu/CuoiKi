# Kịch bản trình diễn bộ lọc VN30 và HNX30

Mở `RUN_APP.ps1`. Giữ cấu hình demo và giới thiệu mục tiêu thu hẹp danh sách cần nghiên cứu. Các mã, số liệu và sự cố trong video là dữ liệu giả lập.

| Cảnh | Thao tác trên giao diện | Lời trình bày gợi ý |
|---|---|---|
| 1. Bảng điểm | Chọn Bảng điểm giả lập và nhóm VN30. Chuyển HNX30 để chỉ ra hai tập so sánh. | Mỗi mã có bốn điểm thành phần. Điểm và hạng được tính trong nhóm tại mốc chọn. |
| 2. Biểu đồ cột | Xem điểm tổng và lọc một số mã. | Bộ lọc áp dụng sau khi chấm điểm. Điểm của mã đang xem giữ nguyên khi thu hẹp hiển thị. |
| 3. Chi tiết và giá | Mở Chi tiết cổ phiếu, chọn DEMO12 và xem biểu đồ đường. | Đường giá cho thấy dữ liệu đầu vào. Bảng bốn điểm cho thấy vị trí tương đối của mã. |
| 4. Mất kết nối | Chọn Nhật ký SSI mẫu, lần Mất kết nối và phục hồi, mốc 10:00:06. | Giao diện hiện mất kết nối và chờ dữ liệu nền mới. |
| 5. Phục hồi | Chọn 10:00:13 và mở Chất lượng dữ liệu. | Lần kết nối thứ hai có dữ liệu mới. Mẫu chỉ có một mã mỗi nhóm nên chưa đạt ngưỡng 10. |
| 6. Dữ liệu cũ | Chọn lần Dữ liệu khối ngoại cũ. | Khối ngoại 63 giây tuổi vượt ngưỡng dự án 60 giây. Tệp CSV giữ nguồn, mốc, tập mã và cấu hình. |

## Ví dụ cho phần bảo vệ

- HOSETEST11 thuộc mẫu kiểm thử toàn tuyến 22 mã. Điểm 100/0/100/20 cho tổng 55 và hạng 4. Trọng số 40/20/20/20 cho tổng 64 và hạng 1.
- Với VN30 còn 9 mã hợp lệ, bảng để trống hạng của cả nhóm. HNX30 cùng mốc vẫn xếp hạng 11 mã.
- Cùng một mốc và cấu hình cho cùng điểm và hạng khi phát lại. Tập mã thay đổi sẽ có mã định danh khác.
- Khi có dữ liệu SSI thật, cần đối chiếu đơn vị, thời điểm nguồn, phạm vi khớp và độ phủ nhiều phiên trước khi diễn giải kết quả.
