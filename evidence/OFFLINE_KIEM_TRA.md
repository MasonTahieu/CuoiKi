# Kiểm tra bản chuẩn bị offline

Ngày: **26/10/2026**. Python 3.13.15, môi trường chung `C:\Users\Hieu\.venv`.

## Kết quả

- **50/50 kiểm thử đạt**, lần chạy cuối 7,41 giây, không cảnh báo.
- Báo cáo máy đọc: [offline-tests.xml](offline-tests.xml).
- Pipeline giả lập: **38 sự kiện**, gồm 36 snapshot của 12 mã hư cấu và 2 sự kiện universe/phiên.
- Lưu SQLite rồi phát lại tại 09:30 và 09:40 UTC+7: 12 mã đủ điều kiện, có bảng xuất CSV ghi nguồn/run.
- Chạy lại fixture không tạo bản ghi trùng; cùng pipeline dùng cho dữ liệu đã lưu.
- `readiness`: không gọi mạng; báo thiếu token/device/WSS như kỳ vọng.
- `collect --transport rest` khi chưa cấu hình token: bị chặn trước khi tạo client/kho hay gửi mạng.
- Streamlit AppTest: mở giao diện, lọc một mã, lọc rỗng, không thay kho live bị thiếu bằng demo.
- Đã mở trang cục bộ và quan sát nhãn giả lập, 12 mã, điểm và bảng xếp hạng.

## Những hành vi đã được kiểm tra

| Nhóm | Bằng chứng chính |
|---|---|
| REST mock | Đọc đủ trang, chống trùng/thiếu/thay đổi tổng, header, không redirect, khoảng cách gọi |
| Lỗi | 401/403 không retry; 429 theo Retry-After; 5xx/timeout giới hạn 3 lần; JSON/nghiệp vụ sai dừng |
| Bảo vệ phạm vi | Không có route giao dịch; WSS sai host/path hoặc WS bị từ chối; lỗi không lộ sentinel |
| WS mock | Auth trước subscribe; auth lỗi không subscribe; mất kết nối lấy lại snapshot và đăng ký lại |
| Nhật ký | Không lưu auth response/token; nguồn/run rõ; SQLite tái tạo đúng trạng thái |
| Chuẩn hóa | Thiếu/null, chuỗi số, giá ATO/ATC, âm/không hợp lệ, số cộng dồn giảm |
| Thời gian | Bỏ dữ liệu sau mốc replay, không ghi đè bằng thời gian nhận cũ, ngắt kết nối xóa baseline |
| Patch | Vắng giữ cũ, null xóa giá trị, đồng hồ từng trường, tự dùng chế độ của run |
| Điểm | Ví dụ tính tay động lượng/ngoại/spread/độ sâu/cung–cầu, phân vị hòa, tối thiểu nhóm, trọng số |
| Xếp hạng | Điểm 0–100, dấu vết cấu hình/nhóm, chống trùng mã; hòa số thực không bị tách hạng |
| Cổng dữ liệu thật | Chưa xác minh ngữ nghĩa thì không có điểm tổng thật |

Kiểm thử chặn kết nối ra Internet, chỉ cho loopback phục vụ bộ kiểm thử UI trên Windows.
Các kết nối REST/WS thành công trong test đều là mock, **không phải VPBS đã cấp quyền hoặc tích hợp thực đã thành công**.

## Cách tái chạy

```powershell
& "$HOME\.venv\Scripts\Activate.ps1"
python -X utf8 -m pytest -q --junitxml=evidence/offline-tests.xml
python -X utf8 -m src.cli demo-pipeline
python -X utf8 -m src.cli replay --db runtime/synthetic.sqlite --as-of 2026-10-26T09:30:00+07:00
python -X utf8 -m src.cli readiness
```

## Chưa nghiệm thu

P1: quyền/IP, URL WSS, schema thực, snapshot/patch, đơn vị, phạm vi khối ngoại, độ trễ nguồn.
P3/P7: nhiều phiên thật, đo độ phủ/hiệu năng và độ nhạy ngoài mẫu; đối chiếu đủ 24 tình huống gốc.
50 test phần mềm không tương đương 24 tình huống nghiệp vụ đã hoàn tất với dữ liệu thật.
P8/P9: báo cáo/video, quyền chia sẻ dữ liệu và gói nộp.
