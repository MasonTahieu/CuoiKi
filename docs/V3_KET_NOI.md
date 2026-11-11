# Kết nối SSI FastConnect API V3

**Cập nhật 06/11/2026.** Phần mềm đã sẵn sàng cho V3 và đã kiểm thử với dữ liệu giả lập đúng định dạng gói tin. **Chưa kết nối SSI thật.** Khi có khóa, bạn làm theo thứ tự ở mục 3. Kết quả từ dữ liệu giả lập không dùng làm bằng chứng về dữ liệu SSI.

## 1. Vì sao chọn V3

- Đề cập nhật cho phép dùng thêm *SSI FastConnect API* và dẫn tới [developers.ssi.com.vn](https://developers.ssi.com.vn/docs/getting-started/overview). Đây là cổng tài liệu của V3.
- Trang [đăng ký](https://developers.ssi.com.vn/docs/getting-started/registration) chỉ còn hướng dẫn FastConnect API: gọi 1900545471 hoặc đến chi nhánh, ký hợp đồng điện tử, sau đó nhận email kích hoạt trong 2–4 giờ làm việc.
- SSI phát hành SDK Python [`ssi-sdk`](https://pypi.org/project/ssi-sdk/3.3.2/). Dự án khóa phiên bản **3.3.2** (yêu cầu Python 3.10 trở lên).
- Nhánh FCData v2 vẫn giữ làm dự phòng. Nếu SSI cấp ConsumerID và ConsumerSecret thì dùng `SSI_API_PROFILE=fcdata_v2`.

## 2. Phần mềm đã chuẩn bị gì

| Thành phần | Tệp | Vai trò |
|---|---|---|
| Cấu hình | `src/ssi_api/settings.py`, `.env.example` | Profile `fastconnect_v3`, API Key/Secret, chế độ OTP, cách đăng ký topic |
| Địa chỉ | `src/ssi_api/connections.py` | Chỉ nhận `https://api.ssi.com.vn` và `wss://stream.ssi.com.vn/ws/v3`. Địa chỉ khác bị từ chối trước khi gửi khóa |
| Đăng nhập và REST | `src/ssi_api/v3_client.py` | Đăng nhập không OTP, OTP SMS/email hoặc Smart OTP. Chỉ gọi các route dữ liệu thị trường. Đọc JSON gốc nên trường thiếu không bị đổi thành 0 |
| Giải mã | `src/ssi_api/v3_decoder.py` | `trade`, `quote`, `room`, `market.flag`, `market.<mã>` sang bản ghi nội bộ dùng chung với v2 |
| Stream | `src/ssi_api/v3_stream.py` | Bọc `WebSocketClient` của SDK và tắt tự nối lại. Mỗi lần nối lại collector tạo một lần kết nối mới và chờ dữ liệu nền mới |
| Vận hành | `src/ssi_api/v3_ops.py`, `SSI_V3.ps1` | Smoke test, thu theo khung giờ, lấy lịch sử nhiều phiên, đối chiếu stream với REST |
| Đánh giá | `src/analytics/sessions.py` | Độ phủ theo mốc, độ ổn định hạng, độ nhạy trọng số, khoảng cập nhật để chọn ngưỡng dữ liệu cũ |
| Kiểm thử | `tests/test_ssi_v3.py` | 43 ca offline, gồm phát lại một nhật ký V3 trên giao diện Streamlit |

### Dữ liệu dùng từ V3

| Nguồn | Trường gốc | Tên nội bộ | Dùng cho |
|---|---|---|---|
| `trade.<rổ>@*` | `p`, `q`, `v`, `o`, `h`, `l`, `a`, `t` | closePrice, lastTradeVolume, totalTradingVolume, openPrice, highPrice, lowPrice, averagePrice | Động lượng, thanh khoản |
| (suy ra) | `a × v` | totalTradingValue | Mẫu số thanh khoản và khối ngoại. Có cảnh báo `TOTAL_VALUE_DERIVED` |
| `quote.<rổ>@*` | `bids`, `asks` = `[[giá, KL], …]` | bid/askPrice1–3, bid/askVol1–3 | Chênh lệch, độ sâu, cung–cầu |
| `room.<rổ>@*` | `bq`, `bv`, `sq`, `sv`, `tr`, `cr` | foreignBuy/SellVolume, foreignBuy/SellValue, foreignRoom, foreignRemain | Dòng tiền ngoại |
| `market.flag` | `b`, `f`, `t` | tradingSession của cả sàn, trải xuống từng mã | Chỉ chấm điểm khi ở phiên LO |
| REST `securitiesByBoard?index=` | `symbol`, `board` | Thành phần VN30 | Danh sách mã của mỗi lần kết nối |
| REST `securitiesSummary` | `open`, `close`, `totalMatch`, `totalMatchValue`, `totalForeignBuy(Value)`… | Dữ liệu ngày | Đối chiếu cuối phiên và phân tích nhiều phiên |

### Khác biệt so với v2 và cách đã xử lý

| Vấn đề | Cách xử lý | Cần xác nhận bằng dữ liệu thật |
|---|---|---|
| V3 không gửi trạng thái từng mã (NORMAL/HALT) | Không yêu cầu `tradingStatus`. Ghi cảnh báo `SYMBOL_STATUS_NOT_PROVIDED` | Có topic nào báo mã bị tạm ngừng hay không |
| Cờ phiên chỉ phát khi đổi phiên, nên có thể lỡ nếu bắt đầu thu giữa phiên | Suy phiên theo lịch giao dịch HOSE/HNX. Ghi cảnh báo `SESSION_FROM_SCHEDULE` | Giá trị thật của `f` và thời điểm phát |
| Gói trade không có tổng giá trị khớp | `a × v`, gắn cờ suy ra. Đối chiếu với `totalMatchValue` của REST lúc 15:05 | **Đã ủng hộ trên dữ liệu ngày thật** (07/11): trung vị `average × totalMatch / totalMatchValue` = 1,0000 trên 599 dòng. Vẫn cần đối chiếu stream/REST |
| `securitiesSummary?index=` | **Quan sát 07/11:** trả về chính chỉ số, không phải các mã thành phần | Code lấy theo từng mã (`symbol=`), 60 lần gọi, giới hạn 2 lần/giây |
| Khối ngoại để trống ở dữ liệu ngày | 43,5% dòng HNX30 trả null, VN30 1,6%. Đây là một lý do bỏ HNX30 | Null có thể nghĩa là "không giao dịch". Đối chiếu với gói `room` trước khi đổi thành 0 |
| Không rõ giá trị ngoại là số ước tính hay số sở báo | `foreign_value_estimated=None`, `foreign_value_basis=pending_live_validation` | Đối chiếu `bv/sv` với REST và với cách tính theo khối lượng |
| Định dạng thời gian `t` chưa được tài liệu nêu rõ | Đọc được epoch ms/s, ISO và HH:MM:SS. Giờ thiếu ngày thì gắn `SOURCE_DATE_FROM_RECEIVED` | Smoke test ghi lại dạng thật |
| Server chỉ giữ một phiên đăng nhập cho mỗi apiKey | Một tiến trình dùng chung một đăng nhập cho REST và stream | Không chạy hai lệnh SSI cùng lúc |

## 3. Khi có khóa: thứ tự thực hiện

1. Mở `.env` (không dán khóa vào chat), điền:
   ```text
   SSI_API_PROFILE=fastconnect_v3
   SSI_API_KEY=...
   SSI_API_SECRET=...
   SSI_OTP_MODE=prompt        # hoặc smart nếu tài khoản dùng Smart OTP
   ```
2. Kiểm tra cấu hình. Lệnh này không gọi mạng:
   ```powershell
   .\SSI_V3.ps1 -Lenh kiemtra
   ```
3. **Smoke test trong giờ giao dịch** (9:20–11:20 hoặc 13:05–14:25), stream 60 giây:
   ```powershell
   .\SSI_V3.ps1 -Lenh smoke -Giay 60
   ```
   Kết quả nằm trong `evidence/v3_smoke/<thời điểm>/SMOKE.md`. Kiểm tra:
   - đủ 30 mã mỗi nhóm;
   - có cả bốn loại `TRADE`, `QUOTE`, `ROOM`, `MARKET_FLAG`;
   - số lỗi giải mã bằng 0;
   - dạng thời gian nguồn;
   - số mức sổ lệnh;
   - tỷ lệ đối chiếu với REST.

   Nếu ack báo `Denied (scope)`, thử lại với `SSI_V3_SUBSCRIBE=symbols` hoặc hỏi SSI về quyền stream.
4. **Lấy lịch sử 10 phiên** (REST, không cần OTP). Đây là bước đáp ứng yêu cầu "≥ 5 phiên" của đề ngay khi có khóa:
   ```powershell
   .\SSI_V3.ps1 -Lenh lichsu -SoPhien 10
   ```
5. Sửa bộ giải mã nếu smoke test cho thấy sai khác, rồi chạy lại test:
   ```powershell
   python -X utf8 -m pytest -q
   ```
6. **Thu mỗi ngày giao dịch**, ít nhất 5 ngày. Mở PowerShell lúc khoảng 8:50 và giữ cửa sổ mở đến 15:05:
   ```powershell
   .\SSI_V3.ps1 -Lenh phien
   ```
   Lệnh tạo hai lần thu (sáng và chiều), lưu vào `runtime/ssi.sqlite`, lấy dữ liệu ngày lúc 15:05 và ghi `evidence/v3_sessions/session-<ngày>.json`.
7. **Đánh giá** sau các phiên đã thu:
   ```powershell
   .\SSI_V3.ps1 -Lenh danhgia
   ```
   Kết quả nằm trong `evidence/v3_sessions/evaluation.json`.
8. Chỉ đặt `SSI_SEMANTICS_VERIFIED=true` khi đủ bằng chứng ở mục 4. Trước đó giao diện vẫn khóa điểm của dữ liệu thật.

## 4. Điều kiện để bật SSI_SEMANTICS_VERIFIED

| Kiểm tra | Bằng chứng | Ngưỡng đề xuất |
|---|---|---|
| Đơn vị giá và khối lượng | Smoke test và đối chiếu REST | Trung vị tỷ lệ `totalTradingVolume` stream/REST trong khoảng 0,99–1,01 |
| Giá trị khớp suy ra | Đối chiếu ở 15:05 | Trung vị tỷ lệ `totalTradingValue` trong khoảng 0,98–1,02. Nếu lệch, bỏ `a × v` và dùng nguồn khác |
| Khối ngoại | Đối chiếu `bv/sv` với REST | Cùng thứ tự độ lớn. Ghi rõ là số ước tính hay số chính xác |
| Phiên | Cờ `market.flag` trong các ngày thu | Nhận được LO, ATC trên HOSE |
| Thời gian nguồn | Dạng `t` và độ trễ ghi nhận | Không có chênh âm lớn hơn 5 giây |

## 5. Ngưỡng dữ liệu cũ phải chọn từ dữ liệu thật

Ngưỡng hiện tại lấy từ bản thu thật buổi chiều 09/11/2026, chưa có phiên sáng và ATO. [Số liệu](../evidence/v3_smoke/20261109-dong-cua/KET_QUA.md)

| Cụm trường | Tuổi tối đa | Trễ tối đa | Căn cứ đo được |
|---|---|---|---|
| Khối ngoại | 100 giây | 35 giây | Gói đến 60 giây một lần, trễ đến 30,5 giây. Lỡ một đợt thì tuổi vượt 120 giây nên vẫn bị phát hiện |
| Giá, khớp lệnh, sổ lệnh | 120 giây | 10 giây | Trễ dưới 1,65 giây, nhưng có mã không khớp lệnh 100 giây dù kết nối tốt |

Mã trong `QualityPolicy` là `V3_LIMITS`. Sau 5 phiên, đọc `update_intervals` trong `evaluation.json` để kiểm tra lại: các phân vị p50, p90, p95, p99 và tỷ lệ cập nhật trong 30, 60, 120, 300, 600 giây theo từng cụm trade, quote, foreign. Đây là căn cứ thống kê cho ngưỡng mà đề yêu cầu ở Mục 7.

## 6. Giới hạn đã biết

- Thu tự động bằng `.github/workflows/ssi-stream.yml` chỉ giữ bản tóm tắt trong `evidence/v3_sessions/stream/`. Lịch của GitHub có thể trễ hoặc bị bỏ qua, nên một khung có thể thiếu dữ liệu đầu giờ hoặc thiếu cả khung.
- Token SSI sống 15 phút và SDK mở lại kết nối mỗi khoảng 14 phút. ROOM không gửi lại khi vừa đăng ký, nên khoảng 1 phút sau mỗi lần đó có mã chưa có số khối ngoại và tạm không xếp hạng. Bộ thu không giữ dữ liệu nền qua các lần nối lại, đây là chủ đích.
- Từ bản sửa 11/11/2026, với `--otp-mode none`, nếu REST hoặc bước lấy/đổi token WebSocket bị từ chối xác thực, client đăng nhập lại một lần rồi thử lại thao tác. Nếu xác thực vẫn thất bại, client vô hiệu hóa phiên, bộ thu ghi `auth_failed` và dừng. Nhật ký chỉ ghi thông báo cố định. Chế độ `prompt` và `smart` tiếp tục yêu cầu người dùng xác thực bằng OTP. Đã kiểm thử offline, cần theo dõi thêm khi thu thật.
- `securitiesByBoard?index=VN30` có lúc chỉ trả một dòng là chính chỉ số. Mã từ chối kết quả đó, dùng lại thành phần của phiên đầy đủ gần nhất và ghi `member_warning`. Nếu rổ VN30 vừa đổi, cảnh báo này cần được đọc.
- Smoke test và lệnh `phien` cần người ngồi máy để nhập OTP nếu SSI yêu cầu. Task Scheduler không nhập OTP thay được.
- Dữ liệu ngày không có sổ lệnh, nên phân tích nhiều phiên theo ngày chỉ có động lượng, thanh khoản và khối ngoại.
- Lịch giao dịch dùng để suy phiên chưa tính ngày nghỉ lễ. Ngày nghỉ sẽ không có dữ liệu nên mã không được chấm.
- Gói cài offline (`offline_wheels`) cần thêm `ssi-sdk`, `httpx` và `httpcore` khi đóng gói lại ZIP.
