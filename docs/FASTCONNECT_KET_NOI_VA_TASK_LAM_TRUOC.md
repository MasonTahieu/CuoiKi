# FastConnect SSI: cách kết nối và công việc có thể làm trước

> Phạm vi sau đó thu hẹp về **VN30** (07/11/2026). Nội dung dưới giữ nguyên để truy vết. [Lý do](../evidence/v3_history/PHAM_VI_VN30.md)

Ngày khảo sát: **04/11/2026**. Người học xác nhận “FlashAPI” trong yêu cầu là **FastConnect của SSI**.
Không tìm thấy tài liệu FlashAPI riêng trong thư mục Cuối kì; đã đọc tài liệu công khai và các tệp mã nguồn client chính thức SSI.
Người học chưa đăng ký SSI, nên kết quả dưới đây là đối chiếu hợp đồng và kiểm thử offline, không phải kết nối thành công.

## 1. Tài liệu đã đọc và căn cứ chọn đường dẫn

| Nguồn chính thức | Nội dung dùng để chuẩn bị |
|---|---|
| [FCData connection guide](https://guide.ssi.com.vn/ssi-products/fastconnect-data/connection-guide) | Host REST/streaming theo môi trường client |
| [FCData sample client guide](https://guide.ssi.com.vn/ssi-products/fastconnect-data/sample-client-guide.md) | Quy trình cấu hình và sử dụng client Python |
| [FCData API specs](https://guide.ssi.com.vn/ssi-products/fastconnect-data/api-specs) | Token, thành phần chỉ số, giá ngày/intraday và phân trang |
| [FCData streaming](https://guide.ssi.com.vn/ssi-products/fastconnect-data/streaming-data) | F, X/Quote/Trade, R, B; trường dữ liệu và ví dụ envelope |
| [SSI Python client README](https://github.com/SSI-Securities-Corporation/python-fcdata) | Tên gói ssi-fc-data, lớp client và cách cấu hình |
| [config.py](https://github.com/SSI-Securities-Corporation/python-fcdata/blob/master/config.py) | Host REST và stream thực tế của sample |
| [model/api.py](https://github.com/SSI-Securities-Corporation/python-fcdata/blob/master/ssi_fc_data/model/api.py) | Các đường dẫn api/v2/Market và SignalR hub |
| [fc_md_client.py](https://github.com/SSI-Securities-Corporation/python-fcdata/blob/master/ssi_fc_data/fc_md_client.py) | Cách lấy token và đính kèm Bearer khi GET |
| [fc_md_stream.py](https://github.com/SSI-Securities-Corporation/python-fcdata/blob/master/ssi_fc_data/fc_md_stream.py) | SignalR, Broadcast và SwitchChannels |
| [V3 overview](https://developers.ssi.com.vn/docs/getting-started/overview) | Nhánh API Key/Secret, REST và WebSocket V3 |
| [V3 token](https://developers.ssi.com.vn/docs/getting-started/api-keys) | URL token/refresh và ví dụ market data |

Các trang SSI có nội dung cũ/mới cùng tồn tại. Một số lần truy cập web chỉ tải được phần khung trang hoặc lỗi;
những nội dung ghi ở đây dựa trên các lần đọc được đầy đủ, đối chiếu source client và kết quả tìm kiếm chính thức.
Không coi thời điểm máy tìm kiếm crawl là ngày phát hành giao thức.

## 2. Kết luận về cách kết nối

### 2.1. FCData v2: REST + SignalR qua client Python

Luồng dự kiến:

```text
ConsumerID + ConsumerSecret
        → POST AccessToken
        → accessToken
        → REST lấy nhóm/mã và dữ liệu khởi tạo
        → client SSI kết nối SignalR
        → đăng ký dữ liệu của các mã thuộc VN30/HNX30
        → lưu bản thô, chuẩn hóa, ghép trạng thái theo từng trường
        → kiểm tra đủ/mới → chấm điểm riêng từng nhóm
```

Địa chỉ đã chuẩn bị theo source chính thức:

| Thành phần | Đường dẫn/cơ chế |
|---|---|
| REST base của client hiện đọc | `https://fc-data.ssi.com.vn/api/v2/Market/` |
| Lấy token | `POST .../AccessToken` với consumerID/consumerSecret |
| Dùng token | Header `Authorization: Bearer <accessToken>` |
| Thành phần chỉ số | `GET .../IndexComponents`, indexCode=VN30 hoặc HNX30 |
| Danh sách chỉ số | `GET .../IndexList` |
| Danh sách chứng khoán | `GET .../Securities`, `.../SecuritiesDetails` |
| Dữ liệu nến | `GET .../DailyOhlc`, `.../IntradayOhlc` |
| Dữ liệu ngày | `GET .../DailyStockPrice`, `.../DailyIndex` |
| Host stream cho config của client Python | `https://fc-datahub.ssi.com.vn/` |
| Địa chỉ SignalR sau khi client ghép path | `https://fc-datahub.ssi.com.vn/v2.0/signalr` |
| Hub | `FcMarketDataV2Hub` |
| Nhận dữ liệu | Callback `Broadcast` |
| Đăng ký/đổi nhóm dữ liệu | Client gọi `SwitchChannels` |

Guide có chỗ nêu REST `/v2.0/Market`; tệp `model/api.py` của client lại ghép `/api/v2/Market`.
Bộ REST dự án dùng nhánh đã đối chiếu source client. Không tự đổi qua lại URL khi gặp lỗi xác thực;
khi được SSI cấp dịch vụ phải xác nhận đúng hướng dẫn của phiên bản đó.

**Điểm quan trọng:** SignalR có bước kết nối và thông điệp riêng. Không gửi JSON auth/sub của NEO trực tiếp tới host SSI.
`SSI_STREAM_BASE` dành cho config client phải là host gốc; không đưa URL đã có `/v2.0/signalr` vào SDK rồi để nó ghép path lần nữa.

### 2.2. FastConnect V3: hợp đồng riêng

| Thành phần | Địa chỉ theo Developer Portal |
|---|---|
| REST base | `https://api.ssi.com.vn/api/v3/` |
| Token | `POST .../auth/token`, dùng apiKey/apiSecret |
| Refresh | `POST .../auth/refresh` |
| Ví dụ tra cứu mã theo sàn | `GET .../data/securitiesByBoard?board=HOSE` |
| Stream | `wss://stream.ssi.com.vn` |
| Tên topic liên quan | trade, quote, room, market |

Tên topic không phải một frame subscribe hoàn chỉnh. Cần đọc hợp đồng frame và scope của phiên bản được cấp trước khi triển khai.
Không tái sử dụng ConsumerID hoặc frame SignalR của FCData cho V3.
Tài liệu overview và SDK có điều kiện xác thực streaming cần đối chiếu thêm; chưa khẳng định market-data token không OTP đủ quyền stream.
Chưa đoán các endpoint V3 còn lại. Chưa chọn UAT/Production hoặc tự lấy quyền nào ngoài tài khoản được SSI cấp.

## 3. Dữ liệu phải ghép để tính bốn yếu tố

| Nhóm dữ liệu FCData | Mục đích | Lưu ý khi làm adapter |
|---|---|---|
| IndexComponents | Thành phần VN30/HNX30 | Đọc đủ trang, tổng đúng, không trùng; lưu lịch sử nhóm |
| F | Phiên và trạng thái từng mã | Ánh xạ N/H, LO/ATO/ATC/BREAK/C; không giả định NORMAL |
| X snapshot / X-Trade | Giá khớp và số liệu giao dịch | Phân biệt last volume với tổng; giữ timestamp nguồn |
| X-Quote | Spread, độ sâu, cung–cầu | Chuẩn hóa cùng ba mức trên hai sàn; không tự điền mức thiếu = 0 |
| R | Khối ngoại | Kiểm tra BuyVal/FBuyVal và tên tương tự theo payload thực; đánh dấu ước tính |
| B | Giá OHLC cập nhật | Không dùng volume phát sinh làm tổng thanh khoản; trường Value có tài liệu nói chưa dùng |
| DailyStockPrice/OHLC REST | Đối chiếu, lịch sử, bootstrap khi phù hợp | Không coi dữ liệu ngày là sổ lệnh tại một thời điểm |

Ví dụ FCData thường bọc dữ liệu trong `DataType` và `Content`; Content có thể là chuỗi JSON cần giải mã thêm.
Không dùng parser bare của NEO cho payload này. Với mỗi loại thông điệp chỉ cập nhật trường có mặt;
null vẫn là thiếu, còn trường vắng cần theo hợp đồng patch được xác minh.

Tài liệu R nêu giá trị ngoại HOSE có thể ước tính từ khối lượng × giá gần nhất. Không coi là dòng tiền giá trị chính xác,
không bắt buộc số đó tăng đơn điệu, và không dùng cập nhật Quote để làm mới thời gian của R.
Xếp hạng mỗi nhóm riêng để tránh các mã thanh khoản lớn của nhóm khác thay đổi phân vị.

## 4. Đã chừa đường dẫn trong dự án ở đâu?

| Tệp | Vai trò và mức hoàn thành |
|---|---|
| `src/ssi_api/connections.py` | Danh mục URL, protocol và các route được tài liệu xác nhận; không có khóa |
| `config/ssi_connection_profiles.json` | Bản xuất để xem hai nhánh kết nối, có nguồn và cờ đã/chưa triển khai |
| `.env.example` | Ô trống profile, khóa, REST/stream base và kho dữ liệu; không điền bí mật vào mẫu |
| `src/ssi_api/settings.py` | Đọc đúng bộ cấu hình SSI, mặc định unselected |
| `src/ssi_api/rest.py` | REST FCData v2 đã chuẩn bị, kiểm tra URL trước khi gửi khóa |
| `src/ssi_api/collector.py` | Probe thành phần và dữ liệu ngày; chưa phải collector realtime |
| `src/providers.py` | Tách SSI và nhánh NEO cũ |

Lệnh xem cấu trúc đường dẫn, không gọi API và không đọc giá trị khóa:

```powershell
& "$HOME\.venv\Scripts\Activate.ps1"
python -X utf8 -m src.cli connection-plan
```

`config/ssi_connection_profiles.json` là bản mô tả đã xuất, không phải tệp chương trình tự đọc để đổi host.
Runtime REST sử dụng `connections.py` và SSI_REST_BASE nếu được cấu hình đúng allowlist; stream base mới là chỗ dự trữ,
chưa có bộ streaming tự sử dụng nó. Chưa điền khóa, cài SDK hoặc gọi SSI thật trong lần chuẩn bị này.

## 5. Danh sách công việc làm được trước khi có tài khoản SSI

Quy ước: `[x]` đã có trong phạm vi ghi rõ; `[ ]` có thể triển khai tiếp offline. Đây không phải checklist đã nghiệm thu live.

### S01 — Hợp đồng và cấu hình kết nối
- [x] Tách FCData v2/V3, xác thực/protocol/đường dẫn và nguồn tài liệu.
- [x] Mẫu cấu hình trống; không dùng khóa NEO cho SSI.
- [x] Lệnh connection-plan xem đường dẫn offline.
- [ ] Kiểm tra cài/import đúng SDK trên Python hiện tại trong môi trường cho phép; chốt phiên bản phụ thuộc.
- [ ] Viết interface chung authenticate/get_components/stream/close, adapter theo profile; phân biệt configured/connected/validated.

### S02 — Bộ giải mã và ánh xạ SSI

Cập nhật 04/11/2026: đây là **Task 1** trong chuỗi bảy task mà người học yêu cầu làm lần lượt.
Đã hoàn thành decoder offline F/X/Quote/Trade/R/B, dấu thời gian và cờ ước tính;
[hợp đồng và cách kiểm tra](TASK_1_GIAI_MA_SSI.md). Collector task 2 và replay task 3 đã hoàn thành offline.

- [x] Viết decoder DataType/Content theo ví dụ chính thức, xử lý Content object hoặc chuỗi JSON.
- [x] Map F/X/Quote/Trade/R/B sang schema nội bộ, kiểm thử tên trường khác nhau và phát hiện mâu thuẫn.
- [x] Có source_at, received_at, field_updated_at và cờ ước tính cho khối ngoại.
- [x] Chuẩn hóa trạng thái từng mã, ba mức giá và ngày giao dịch; đơn vị ghi rõ còn chờ xác minh thực tế.

### S03 — Collector với nguồn mô phỏng

Cập nhật: **Task 2** hoàn thành collector offline, ghép patch theo từng trường, reconnect, sink và kịch bản kiểm tra.
Xem [hợp đồng và giới hạn task 2](TASK_2_COLLECTOR_GIA_LAP.md). Task 3 đã thêm ghi theo lô và kiểm tra chất lượng.

- [x] REST v2 probe và kho nguồn/run đã có.
- [x] Viết collector streaming theo interface; dùng fake stream để kiểm thử trước.
- [x] Ghép cập nhật từng phần, reconnect/backoff, reset baseline và đăng ký lại sau kết nối — kiểm thử fake stream.
- [x] Task 3: bộ đệm có giới hạn, ghi SQLite theo lô và rollback; pull tuần tự tạo backpressure.
- [ ] Adapter callback/queue đa luồng có giới hạn và kiểm soát tốc độ theo SDK thật.
- [ ] Chuẩn bị token expiry/refresh theo đúng profile, không retry đăng nhập vô hạn hoặc log bí mật.

### S04 — Dữ liệu và phát lại

**Task 3 hoàn thành offline.** Xem [kết quả mẫu](../evidence/task3/KET_QUA_MAU.md) và [hợp đồng task 3](TASK_3_LUU_TRU_REPLAY_CHAT_LUONG.md).

- [x] Nhật ký SQLite, replay và tách nhóm/nguồn có trong bản nền.
- [x] Fixture dạng SSI cho hai nhóm: hai mã hư cấu, thiếu/cũ/trễ, HALT từng mã và null; kiểm thử khác ngày.
- [x] Báo cáo độ phủ: số mã, từng trường đủ/thiếu, gap được ghi nhận, source age và receive age.
- [x] Chỉ phát lại trường đã xuất hiện tại mốc chọn; kiểm tra không trộn qua ngày hoặc qua gap.
- [x] Xuất CSV/JSON/manifest, kiểm tra hợp đồng decoded và ảnh chụp chỉ đọc khi có writer.
- [ ] Đối chiếu thành phần đủ 30 mã/nhóm và chất lượng nhiều phiên thật; chưa thể làm khi chưa có SSI.

### S05 — Kiểm chứng phương pháp
- [x] Bốn yếu tố, trọng số, hòa hạng, nhóm tối thiểu và xếp hạng riêng có kiểm thử.
- [x] Kiểm thử replay khi giá giảm và giá trị ngoại ước tính giảm, trong khi khối lượng ngoại tăng.
- [x] Đặc tả và kiểm thử tỷ lệ khối lượng ngoại như cấu hình đối chiếu độc lập.
- [x] Tính tay spread, độ sâu, ngoại âm và kiểm tra nhóm thiếu mã.
- [x] Đo đóng góp từng yếu tố và độ nhạy trọng số với 11 mã giả lập mỗi nhóm. [Kết quả mẫu](../evidence/task4/KET_QUA_MAU.md)
- [ ] Xác minh phạm vi, đơn vị và độ nhạy trên dữ liệu SSI thật trước khi chốt phương pháp.

### S06 — Giao diện hoàn chỉnh ở chế độ giả lập
- [x] Chọn VN30/HNX30, lọc mã/điểm/trọng số, chi tiết, biểu đồ cột/đường và CSV.
- [x] Hiển thị trạng thái kết nối, tuổi từng cụm trường, cờ ngoại ước tính và lý do chưa xếp hạng.
- [x] Hiển thị chờ snapshot, gián đoạn, phiên LO hoặc ngoài LO và nhóm thiếu dữ liệu dựa trên bản ghi.
- [x] Chọn lần thu thập và mốc phát lại, tùy chọn làm mới kho live và xuất CSV kèm cấu hình phương pháp. [Hướng dẫn task 5](TASK_5_GIAO_DIEN.md)

### S07 — Kiểm thử tích hợp offline
- [x] Test mock REST, điểm theo nhóm và UI nền đã có.
- [x] Kiểm thử toàn tuyến gói SSI giả lập → SQLite → replay/chất lượng → bốn yếu tố → điểm/hạng → UI/CSV.
- [x] Đối chiếu T01–T24, có kết quả chạy mã nguồn ở thư mục mới và mốc nghiệm thu gói nộp. [Ma trận kiểm thử](TASK_6_KIEM_THU_TOAN_TUYEN.md)
- [x] Kiểm thử lỗi 429/503/403, timeout, token hết hạn, schema lạ, lỗi adapter giả lập và chặn điểm từ dữ liệu ngày.
- [ ] Đối chiếu quota, lỗi SDK, làm mới token, độ trễ và độ phủ với phiên SSI thật.

### S08 — Báo cáo và gói chạy
- [x] Kế hoạch SSI và tài liệu chuyển đổi đã có.
- [ ] Viết phần bài toán, người dùng, kiến trúc, từ điển và công thức; để trống kết quả thực nghiệm.
- [ ] Lập kịch bản demo có luồng bình thường và tình huống lỗi.
- [ ] Hoàn thiện README, mẫu cấu hình và kiểm tra dựng lại gói, loại thông tin bí mật.

**Thứ tự đề xuất:** S02 → S03/S04 → S05 → S06 → S07 → S08. S01 phần SDK/interface làm cùng S02.
Cập nhật 05/11/2026. Đã hoàn thành task 1–6 offline theo thứ tự bàn giao.

## 6. Khi có bộ khóa: các bước còn bắt buộc

1. Chọn profile/host đúng dịch vụ SSI đã cấp; xác nhận scope và hạn mức thực tế.
2. Đăng nhập cục bộ; đọc index list, đủ thành phần VN30/HNX30 và một số snapshot để đối chiếu.
3. Kết nối stream trong giờ giao dịch; xác minh schema, đơn vị, timestamp, phiên, snapshot/patch và ngoại ước tính.
4. Sửa adapter nếu có sai khác, chạy lại regression tests; chỉ bật SSI_SEMANTICS_VERIFIED sau khi có căn cứ.
5. Thu nhiều phiên để đo độ phủ, độ trễ/hiệu năng và kiểm chứng phương pháp trước khi chốt kết quả báo cáo.

Có thể làm trước phần lớn phần mềm để giảm công việc tích hợp. Không thể bảo đảm chỉ dán khóa là hoàn tất nghiệm thu:
quyền truy cập, schema thực và chất lượng phương pháp vẫn cần dữ liệu thật.
