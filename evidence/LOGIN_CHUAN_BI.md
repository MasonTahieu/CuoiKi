# Chuẩn bị đăng nhập — 04/11/2026

- PyPI API vpx-neo-sdk trả HTTP 404; chưa cài hoặc thêm dependency không tồn tại.
- Endpoint xác thực đối chiếu trang tài liệu: https://external.vpbanks.com.vn/auth/token.
- Đã thêm nhập tài khoản hiển thị và mật khẩu ẩn cục bộ, không theo redirect, không retry đăng nhập, không in token/body lỗi.
- Access token lưu .env đã bị loại khỏi Git; giữ nguyên cấu hình khác; không lưu mật khẩu/refresh token.
- Kiểm thử offline toàn bộ: 56 passed trong 15,72 giây; báo cáo offline-tests.xml.
- Chưa gửi thông tin đăng nhập thật hoặc gọi thị trường; chờ người dùng đăng nhập cục bộ.
