# Kết nối khi VPBS cấp quyền

Bản chuẩn bị ngày 26/10/2026. Chưa chạy NEO thật. Không cần gửi token, mật khẩu hoặc OTP vào chat.

## 0. Chưa có token nhưng đã được kích hoạt

Mở `DANG_NHAP_NEO.cmd` trong thư mục dự án. Nhập số lưu ký và mật khẩu trực tiếp
vào cửa sổ trên máy; công cụ gọi `https://external.vpbanks.com.vn/auth/token` đúng tài liệu,
lưu access token vào `.env` và không lưu mật khẩu/refresh token.
Không gửi thông tin đăng nhập vào chat. Nếu lỗi thì dừng; không tự thử lại nhiều lần.

## 1. Điền cấu hình

Tại thư mục dự án, sao chép `.env.example` thành `.env` **nếu chưa có**; không ghi đè cấu hình đang dùng.
Điền access token do luồng chính thức cấp, device ID và device type phù hợp tài khoản.
Chỉ token chưa đủ nếu IP/quyền hoặc URL kết nối chưa được VPBS xác nhận.

```dotenv
APP_MODE=demo
NEO_ACCESS_TOKEN=<access_token thực tế, không kèm Bearer>
NEO_DEVICE_ID=<thiết bị đã đăng ký/phù hợp hướng dẫn VPBS>
NEO_DEVICE_TYPE=chrome
NEO_WS_URL=<URL WSS thị trường được VPBS xác nhận>
NEO_WS_FORMAT=bare
NEO_UPDATE_MODE=snapshot
NEO_SEMANTICS_VERIFIED=false
NEO_DATABASE=runtime/neo.sqlite
```

Không chép dấu `<...>` ở trên như giá trị thật. `.env` đã nằm trong `.gitignore`.
Token chỉ đọc khi chạy lệnh; không được lưu trong nhật ký hoặc mẫu dữ liệu. Collector không tự đăng nhập bằng mật khẩu; công cụ đăng nhập tương tác là lệnh riêng.
Nếu token hết hạn, thay trong `.env`, dừng collector cũ và chạy lại.
Tài liệu cấp token hiện là `https://external.vpbanks.com.vn/auth/token`; chưa tự xây luồng refresh vì thiếu đặc tả xác minh.

## 2. Kiểm tra cục bộ rồi thử REST

```powershell
& "$HOME\.venv\Scripts\Activate.ps1"
python -X utf8 -m src.cli readiness
python -X utf8 -m src.cli collect --transport rest
```

`readiness` không gọi mạng và không in giá trị bí mật. `collect --transport rest` gửi yêu cầu thật chỉ đọc:
đọc đủ trang VN30, lưu snapshot vào SQLite, đọc trạng thái HOSE. Lần thu thập có `run` riêng.
Không chạy lệnh này trước khi quyền/IP được cấp. REST probe không cần URL WS và không thay cho bằng chứng WebSocket của đề.

Các lỗi 401/403 dừng ngay, cần kiểm tra token/quyền/IP. Lỗi JSON, nghiệp vụ, phân trang hoặc mã trùng dừng rõ ràng;
không tự chuyển sang dữ liệu giả lập. Không chia sẻ nội dung `.env` hoặc ảnh có header Authorization.

## 3. Xác minh WSS và cấu trúc thông điệp

Trang tài liệu hiện minh họa `ws://neoapi.vpbanks.com.vn/stock-stream/broker`.
Hãy lấy xác nhận URL **WSS** từ VPBS; chương trình cố ý để trống, không gửi token qua WS không mã hóa.
Allowlist hiện chỉ cho `wss://neoapi.vpbanks.com.vn/stock-stream/broker`, cổng mặc định/443;
đây là dạng được code chấp nhận, **không phải tuyên bố endpoint đã được kiểm tra hoạt động**.
Nếu VPBS cấp host/path khác cần cập nhật bộ kết nối theo thông tin chính thức.

```powershell
python -X utf8 -m src.cli collect --transport ws --seconds 300
```

Collector độc lập: REST bootstrap → WS auth → chờ success → đăng ký stockInfo và marketSession → lưu dữ liệu.
Ngắt kết nối: ghi khoảng gián đoạn → thử lại tối đa 3 lần → lấy lại snapshot và đăng ký lại.
Không giữ trạng thái cũ để chấm xuyên qua khoảng ngắt. Timeout chờ 15 giây; gửi ping, sau ba lần không dữ liệu thì reconnect.
Thông số heartbeat này là cơ chế phòng vệ của ứng dụng, cần hiệu chỉnh bằng phiên thật.

`NEO_WS_FORMAT=bare` hỗ trợ các payload dạng object độc lập như ví dụ tài liệu.
`channel_data` hỗ trợ envelope `{channel, data}` để chuẩn bị, chưa được xác minh là dạng NEO thực tế.
Thông điệp lạ ghi `unrecognized_message`, không lưu body tùy ý và không đưa vào điểm.
Nếu gặp thường xuyên, cần xác định schema thực tế và chỉnh `src/neo_api/stream.py` trước khi nghiệm thu.

## 4. Checklist P1 trước khi mở điểm dữ liệu thật

- [ ] Token, quyền dữ liệu, IP và device hợp lệ; token hết hạn xử lý đúng.
- [ ] URL WSS bảo mật được xác nhận và nhận được auth success.
- [ ] VN30 đủ trang, đúng loại ST/HOSE; ngày giao dịch và thành phần được lưu theo lần thu thập.
- [ ] `closePrice` là giá khớp gần nhất trong phiên, `openPrice` là giá mở cửa cùng ngày.
- [ ] Giá = VNĐ; đơn vị khối lượng chào/giao dịch đã xác minh.
- [ ] Tổng giá trị và mua/bán ngoại có cùng phạm vi khớp lệnh/thỏa thuận; quy tắc cộng dồn/reset đã rõ.
- [ ] Wrapper, snapshot hay patch, null/vắng trường và định dạng timestamp đã được xác minh.
- [ ] `tradingStatus`, phiên LO/ATO/ATC/nghỉ/đóng cửa hoạt động đúng; thử mất kết nối và dữ liệu cũ.
- [ ] Xác định giới hạn thiếu timestamp/sequence; điều chỉnh ngưỡng cũ nếu cần, không gọi received_at là event time.
- [ ] Ghi bằng chứng và sai khác vào `evidence/P1_XAC_MINH_THUC_TE.md` khi có dữ liệu thật.

Chỉ sau các mục trên mới đặt `NEO_SEMANTICS_VERIFIED=true`. Đây là cờ xác nhận thủ công,
không phải chương trình tự chứng minh tính đúng của API. Giữ false thì xem được dữ liệu nhưng không tính điểm thật.

Chỉ chọn `NEO_UPDATE_MODE=patch` sau khi chứng minh trường vắng nghĩa là không cập nhật.
Null hiện hữu vẫn làm mất giá trị; mỗi trường có đồng hồ riêng, không làm mới cả hàng bằng một cập nhật nhỏ.
Bản ghi số liệu cộng dồn giảm bị khóa đến lần khởi tạo lại; cần điều tra nguyên nhân trước khi tiếp tục.

## 5. Xem dữ liệu và phát lại

- `APP_MODE=live`: giao diện đọc lần thu thập mới nhất từ SQLite; nút “Đọc lại kho dữ liệu” làm mới.
  Collector chạy ở cửa sổ riêng. UI không tự kết nối API và chưa tự refresh định kỳ.
- `APP_MODE=replay`: chọn mốc trong lần thu thập mới nhất bằng thanh thời gian.
- `APP_MODE=demo`: 12 mã hư cấu, không cần token và không gửi mạng.

```powershell
.\RUN_APP.ps1
python -X utf8 -m src.cli replay --db runtime/neo.sqlite
# Chọn run cụ thể và thời gian có timezone khi cần:
python -X utf8 -m src.cli replay --db runtime/neo.sqlite --run <run_da_thu_thap> --as-of 2026-10-26T10:00:00+07:00
```

CLI xuất bảng chuẩn hóa kèm điểm, lý do loại, nguồn/run, phiên bản phương pháp, mã nhóm và cấu hình vào `runtime/neo_ranking.csv`.
Tệp CSV cùng nguồn được ghi lại ở lần xuất tiếp theo; SQLite vẫn giữ nhật ký gốc, có thể tái tạo.
Replay tự lấy `update_mode` đã ghi trong connection log của run; chỉ dùng cấu hình hiện tại khi journal không có metadata. Run có nhiều chế độ mâu thuẫn bị từ chối.

## 6. Nghiệm thu sau kết nối

Thu thập tối thiểu số phiên cần cho phân tích (kế hoạch đề xuất 5, ưu tiên 10), đo độ phủ/khoảng trống,
đối chiếu số mẫu với nguồn, kiểm thử các ca tài chính bằng dữ liệu thật, đánh giá độ nhạy trọng số.
Chưa coi bản chạy giả lập là đã hoàn thành P1/P3/P7 hoặc có hiệu quả đầu tư.
Chạy duy nhất một collector cho cùng client để giữ ngân sách tần suất; không có điều phối liên tiến trình.
