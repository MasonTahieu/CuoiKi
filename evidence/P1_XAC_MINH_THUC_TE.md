# P1 — Kiểm tra kết nối thực tế

Thời điểm kiểm tra: 2026-11-04T14:23:18.506652+07:00

- Đã có .env với access token và device ID từ công cụ đăng nhập; không ghi bí mật vào bằng chứng này.
- Gọi GET /stock/stockDetailByIndex với indexCode=VN30 trên market endpoint HTTPS chính thức.
- Phản hồi HTTP 401, status=0, code=NEOINP000401.
- Chưa lấy được danh sách VN30 hoặc dữ liệu giá thật. Chưa thử WebSocket.
- Chưa xác định nguyên nhân cuối cùng: cần kiểm tra token, quyền NeoAPI, IP whitelist và header thiết bị.
- NEO_SEMANTICS_VERIFIED giữ false. Không nghiệm thu P1 và không dùng dữ liệu giả làm kết quả thật.
