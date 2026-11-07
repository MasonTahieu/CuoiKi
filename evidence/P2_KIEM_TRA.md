# Kết quả kiểm tra P2

Ngày kiểm tra: 26/10/2026.

## Môi trường

- Windows; Python 3.13.15.
- Môi trường riêng dùng chung: `C:\Users\Hieu\.venv`.
- Phiên bản phụ thuộc trực tiếp: xem `../requirements.txt`.
- Kiểm tra phụ thuộc: `python -m pip check` trả `No broken requirements found.`

## Kết quả

| Kiểm tra | Kết quả thực tế |
|---|---|
| CLI check | Đọc được 12 quan sát, 4 mã giả lập, múi giờ Asia/Ho_Chi_Minh, neo_connected=false |
| Bộ kiểm thử P2 | 10 passed; xem `p2-tests.xml` |
| Nhãn dữ liệu | Từ chối nguồn khác synthetic hoặc mã không phải DEMOxx |
| Dữ liệu không hợp lệ | Từ chối thời gian thiếu offset, số thiếu/âm và quan sát trùng |
| Giao diện | AppTest khởi động, lọc còn một mã và chọn rỗng đều đạt |
| Cấu hình live | Dừng có thông báo, không tự dùng giả lập thay cho dữ liệu thật |
| Kết nối trong kiểm thử | Chặn socket ra ngoài; chỉ cho phép loopback để Windows chạy AppTest |
| Trang chạy thực tế | Đã mở http://127.0.0.1:8501 và xem giao diện: nhãn giả lập, 4 mã, 12 quan sát, mốc UTC+7 |

Đã sửa lỗi mã hóa tiếng Việt trong CLI Windows và điều chỉnh kiểm thử cho
cơ chế socket nội bộ của Windows. Không có lỗi còn lại trong bộ kiểm thử P2.

## Giới hạn xác nhận

Đây là kiểm tra môi trường và khung P2, không phải kiểm chứng 24 tình huống
nghiệp vụ trong kế hoạch. P1 vẫn chờ API. Chưa gọi NEO, chưa có dữ liệu thị trường
thật, chưa có công thức bốn yếu tố, xếp hạng hoặc bộ thu thập.

Chạy lại từ thư mục dự án: `./CHECK_PROJECT.ps1`. Máy chủ demo chỉ hoạt động
khi tiến trình Streamlit còn chạy; mở lại bằng `./RUN_APP.ps1` nếu đã dừng.

