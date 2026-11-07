# NeoAPI cung cấp gì và dự án dùng phần nào?

Đối chiếu tài liệu công khai v1.0.0 ngày **26/10/2026**. Chưa có quyền API thật.
“Có trong tài liệu” không đồng nghĩa tài khoản đã được cấp quyền, mọi trường luôn có dữ liệu,
hoặc phần mềm đã vượt qua kiểm tra tích hợp thực tế.

## 1. Danh mục chức năng

Các đường dẫn REST thị trường dưới đây ghép sau `https://neoapi.vpbanks.com.vn/neo-api`.

| Nhóm | Nguồn được tài liệu mô tả | Thông tin/chức năng | Phạm vi dự án |
|---|---|---|---|
| Xác thực | `POST https://external.vpbanks.com.vn/auth/token` | `access_token`, loại token, `refresh_token`, thời hạn và thông tin onboarding | Nhận access token từ cấu hình; chưa tự lưu mật khẩu hay tự refresh |
| Tài khoản | Mục 2.1–2.2 | Sức mua và danh sách tài khoản | Không sử dụng |
| Tài sản | Mục 3.1–3.2 | Danh mục cơ sở, vị thế phái sinh | Không sử dụng |
| Danh sách chỉ số | `GET /market/indexList` | Mã/tên chỉ số, sàn, có phân trang | Có sẵn route chỉ đọc; chưa đưa vào điểm |
| Chỉ số intraday | `GET /market/intradayMarketIndex` | Chỉ số, biến động, thanh khoản, độ rộng, chuỗi `index[]` | Có sẵn route; bối cảnh mở rộng |
| Chỉ số trong phiên | `GET /market/marketIndexDetail` | Snapshot chỉ số, tham chiếu, tăng/giảm/trần/sàn, lô lẻ | Có sẵn route; chưa đưa vào điểm |
| Trạng thái thị trường | `GET /market/marketStatus` | Phiên theo sàn, mã chỉ số | Khởi tạo trạng thái HOSE |
| Danh mục chứng khoán | `GET /stock/stockList` | Mã, tên, sàn, loại chứng khoán | Có sẵn route; phục vụ đối chiếu |
| Chi tiết chứng khoán | `GET /stock/stockDetail` | Giá, giao dịch, sổ lệnh, khối ngoại, thông tin bổ sung | Có sẵn route chỉ đọc |
| Cổ phiếu theo chỉ số | `GET /stock/stockDetailByIndex` | Các trường snapshot, lọc VN30 và phân trang | Nguồn chính để lấy nhóm và khởi tạo |
| Lô lẻ | `GET /stock/oddLotStockDetail` | Giá/giao dịch/sổ lệnh lô lẻ, sự kiện; bên bán dùng `offerPrice*`, `offerVol*` | Ngoài bản đầu; không trộn với `ask*` lô chẵn |
| Hợp đồng tương lai | `GET /stock/fuStockDetail` | Giá, sổ lệnh, giao dịch, khối ngoại, đáo hạn, `openInterest` | Ngoài bản đầu; giá theo điểm chỉ số |
| Lệnh | Mục 5.1–5.5 | Đặt/sửa/hủy, sổ lệnh của tài khoản trong ngày, lịch sử lệnh | Không triển khai; đây không phải lịch sử giá thị trường |
| Market Stream | `stockInfo`, `marketSession`, `marketInfo`, `marketVolume` | Dữ liệu thị trường liên tục | Collector đăng ký stockInfo + marketSession |
| Trading Stream | Mục 6.3 | Luồng dữ liệu lệnh/tài khoản liên quan giao dịch | Không sử dụng |
| Phụ lục | Mục 7.1–7.2 | Định nghĩa và mã lỗi | Dùng đối chiếu khi kiểm tra P1 |

Danh mục này tóm tắt toàn bộ **nhóm chức năng**; bảng trường chi tiết dưới đây tập trung vào dữ liệu của đề tài,
không phải bản sao toàn bộ tài liệu tài khoản/lệnh.

Nguồn: [Danh mục tài liệu](https://neoinvest.vpbanks.com.vn/neo-openapi/docs/getting-started/introduction),
[Token](https://neoinvest.vpbanks.com.vn/neo-openapi/docs/auth/token),
[Thị trường](https://neoinvest.vpbanks.com.vn/neo-openapi/docs/market/stock-detail-by-index),
[Market Stream](https://neoinvest.vpbanks.com.vn/neo-openapi/docs/streaming/market-stream).

## 2. Ánh xạ trường phục vụ bốn yếu tố

| Dữ liệu NEO | Khả năng dùng | Quy tắc hiện tại / điểm phải xác minh |
|---|---|---|
| `symbol`, `stockName`, `stockType`, `marketCode`, `exchangeCode` | Nhận diện, phạm vi VN30 | Chỉ HOSE/ST từ endpoint theo chỉ số; không hard-code VN30 |
| `tradingDate`, `tradingStatus` | Kiểm tra ngày và trạng thái | Đúng ngày phân tích; NORMAL mới được chấm |
| `closePrice`, `openPrice`, `refPrice`, `highPrice`, `lowPrice`, `averagePrice` | Động lượng từ mở cửa, biểu đồ | Stream mô tả closePrice là đóng cửa/khớp gần nhất, REST viết đóng cửa; phải đối chiếu thực tế |
| `totalTradingVolume`, `totalTradingValue` | Thanh khoản cộng dồn | Giá trị giảm trong ngày bị gắn lỗi; không tự cộng các snapshot |
| `bidPrice1..3`, `askPrice1..3` | Spread, độ sâu theo giá trị | Chuỗi số chuyển thành số; ATO/ATC không chuyển thành 0 |
| `bidVol1..3`, `askVol1..3` | Độ sâu, mất cân bằng ba mức | Thiếu/null không tự coi là 0; cần xác minh đơn vị cổ phiếu/lô |
| `foreignBuyValue`, `foreignSellValue` | Giá trị ngoại ròng / tổng giá trị | Chỉ bật điểm thật sau khi xác minh tử và mẫu cùng phạm vi khớp lệnh/thỏa thuận |
| `foreignBuyVolume`, `foreignSellVolume` | Đối chiếu dòng tiền | Không thay giá trị bằng khối lượng một cách âm thầm |
| `foreignNetValue` trong stream | Giá trị ròng do nguồn tính | Có trong tài liệu; bản đầu tự tính mua−bán, chưa dùng trường này thay thế |
| `foreignRoom`, `foreignRemain` | Room ngoại | Có thể bổ sung hiển thị; không phải yếu tố điểm hiện tại |
| `ptTotalTradedQTTY`, `ptTotalTradedValue` | Giao dịch thỏa thuận | Dùng xác minh phạm vi, không tự trừ khi chưa biết quan hệ với tổng |
| `totalBidQTTY`, `totalAskQTTY` | Tổng chào | Ví dụ có null; không dùng thay cho tổng ba mức giá |
| `events` và thông tin chứng quyền | Ngày sự kiện/quyền, thông tin công cụ | Không đủ để khẳng định có chuỗi giá đã điều chỉnh |
| `marketSession.marketStatus` | PRE/ATO/LO/ATC/PLO/PT/C | Chỉ LO mới được chấm; chưa có trạng thái thì chờ |
| `marketSession.time` | Thời điểm phiên | Giữ trong nhật ký; timestamp không timezone cần xác nhận UTC+7 ở P1 |
| `marketInfo` | Chỉ số, độ rộng, giá trị/khối lượng, trạng thái | Adapter nhận diện sẵn; collector bản đầu chưa đăng ký |
| `marketVolume.totalVolume`, `volume` | Cộng dồn và phát sinh của chỉ số | Không áp công thức delta này sang stockInfo nếu chưa xác minh |

Nguồn chi tiết: [REST theo chỉ số](https://neoinvest.vpbanks.com.vn/neo-openapi/docs/market/stock-detail-by-index),
[Stream](https://neoinvest.vpbanks.com.vn/neo-openapi/docs/streaming/market-stream),
[Trạng thái](https://neoinvest.vpbanks.com.vn/neo-openapi/docs/market/market-status).

## 3. Giới hạn phải giữ trong phạm vi đề tài

- Có dữ liệu giá/giao dịch nội ngày trong tài liệu. **Chưa xác nhận API lịch sử OHLCV nhiều ngày của từng cổ phiếu.**
  `intradayMarketIndex` là chỉ số; lịch sử lệnh là lệnh của tài khoản. Cả hai không thay thế lịch sử giá cổ phiếu.
- Chưa thấy nguồn báo cáo tài chính doanh nghiệp, phân ngành chuẩn hoặc chuỗi điều chỉnh sự kiện trong danh mục đã đọc.
  Không hứa PE/PB/ROE, RSI/MA nhiều ngày, backtest dài hạn trong phiên bản đầu.
- Dữ liệu lịch sử cho replay hình thành từ lúc tự thu thập, không khôi phục những phiên đã bỏ lỡ.
- Mẫu `stockInfo` không nêu timestamp/sequence riêng của từng cổ phiếu. Bản đầu lưu `received_at` tại máy,
  không gọi đó là thời gian giao dịch tại sàn; không thể bảo đảm phát hiện mọi thông điệp đến muộn từ nguồn.
- Tài liệu cho phép null hoặc vắng trường nhưng chưa chốt ý nghĩa “vắng = không đổi”. Mặc định `snapshot`
  để thiếu trường thì loại; chỉ dùng `patch` sau xác minh. Chế độ patch giữ thời gian từng trường.
- Chưa chứng minh quyền truy cập, số mã tối đa, dữ liệu trong/ngoài giờ, độ trễ và tính ổn định nhiều phiên.

## 4. Hợp đồng kết nối đã chuẩn bị

- REST market HTTPS, `Authorization: Bearer`, `x-device`, `x-devicetype`; không theo redirect.
- Tài liệu token hiện dùng **external.vpbanks.com.vn/auth/token**, không ghép `/auth/token` vào market base.
  Response nêu `expires_in` (ví dụ 10800 giây); dùng thời hạn thực tế khi được cấp, không hard-code 3 giờ.
  Có refresh_token nhưng trang này chưa đủ quy trình refresh để tự đoán endpoint.
- REST tối đa 5 yêu cầu/giây/client theo tài liệu; code giữ tối thiểu 0,3 giây giữa lần thử của một collector.
  Chỉ chạy một collector cho cùng client. Lỗi 429/5xx/timeout thử tối đa 3 lần; 401/403 dừng ngay.
- Phân trang request từ 1; response có số trang nội bộ từ 0. Kiểm tra tổng trang/tổng phần tử và mã trùng.
- WS gửi auth trước, đợi success mới subscribe. Không lưu response auth, không in token hoặc body lỗi.
- Trang stream ghi `ws://neoapi.vpbanks.com.vn/stock-stream/broker`. Phần mềm **chưa điền WSS tự suy đoán**;
  chờ VPBS xác nhận URL bảo mật trên host/path chính thức. Nếu VPBS cấp gateway khác cần sửa allowlist có chủ đích.
- `bare` theo các ví dụ payload; `channel_data` là adapter chuẩn bị cho envelope `{channel,data}`,
  **không khẳng định đó là wire format chính thức**. Gặp dạng khác ghi trạng thái chưa nhận diện, không suy diễn dữ liệu.
- Chỉ nhận các kênh thị trường hỗ trợ; thông điệp chưa nhận diện không lưu nguyên body.

Nguồn: [Quy ước](https://neoinvest.vpbanks.com.vn/neo-openapi/docs/getting-started/conventions),
[Kết nối WS](https://neoinvest.vpbanks.com.vn/neo-openapi/docs/streaming/websocket-connection),
[Intraday index](https://neoinvest.vpbanks.com.vn/neo-openapi/docs/market/intraday-market-index).

## 5. Phạm vi sản phẩm chốt cho giai đoạn chờ API

Đã có mã cho: collector độc lập, REST VN30 + trạng thái HOSE, WS thị trường, SQLite theo lần thu thập,
chuẩn hóa UTC+7, replay theo mốc, bốn yếu tố, xếp hạng, bộ lọc, biểu đồ, tải CSV và kiểm thử offline.
Mẫu chạy thử là **12 mã hư cấu**, không phải chứng cứ chất lượng NEO hay hiệu quả đầu tư.

Khi có quyền: làm [checklist kết nối](KET_NOI_KHI_CO_TOKEN.md), điều chỉnh adapter nếu payload thực khác,
thu thập nhiều phiên rồi kiểm chứng. Không nghiệm thu P1 hoặc dữ liệu thật chỉ vì kiểm thử giả lập đạt.
