# Task 2 — Collector với luồng SSI giả lập

Hoàn thành offline: **04/11/2026**, chờ người học kiểm tra. Chỉ thực hiện task 2 trong chuỗi bảy task.
Không gọi SSI thật và chưa triển khai task 3.

## 1. Kết quả và cách xem

Mở [bảng diễn biến mẫu](../evidence/task2/KET_QUA_MAU.md).

Kịch bản gồm hai mã hư cấu DEMO01 (nhóm minh họa VN30/HOSE) và HNDEMO01 (nhóm minh họa HNX30/HNX),
**15 thông điệp nhận, 14 giải mã thành công, 11 lần ghép, 1 trùng, 2 bị loại, 1 JSON lỗi, 1 lần kết nối lại**.
Hai mã chỉ nhằm kiểm tra cơ chế collector; không phải thành phần thật hoặc số lượng đủ để xếp hạng chỉ số.

Các tệp để kiểm tra:

- `evidence/task2/KET_QUA_MAU.md`: bảng diễn biến dễ đọc và sáu điểm cần xem.
- `evidence/task2/collector_report.json`: kết quả cuối, bộ đếm và trạng thái từng mã.
- `evidence/task2/journal.json`: sự kiện theo thứ tự nhận trong kịch bản, có source/run/connection_epoch.
- `runtime/task2-synthetic.sqlite`: kho riêng cho kịch bản task 2. Mỗi lần chạy thêm run mới.
- `evidence/task2-tests.xml`: kết quả kiểm thử toàn bộ.

Tạo lại kết quả, không cần API/SDK và không gọi mạng:

```powershell
& "$HOME\.venv\Scripts\Activate.ps1"
python -X utf8 -m src.ssi_api.collect_sample
```

JSON và bảng mẫu cùng tên được ghi lại khi chạy lại; SQLite giữ các run riêng.

## 2. Những gì collector đã làm

```text
FakeFactory.bootstrap: danh sách hai nhóm
  → tạo session, connect và gửi ý định đăng ký kênh
  → receive Frame(raw, received_at)
  → decoder task 1
  → lưu thông điệp thị trường đã lọc và kết quả decoder
  → ghép từng trường theo source_at
  → lưu snapshot cùng thời gian/provenance từng trường
```

- `Stream`/`Factory` là interface cho bootstrap, connect, subscribe, receive có timeout và close.
- `FakeFactory` là implementation mô phỏng, nguồn mặc định cố định synthetic, không nhận khóa.
- Collector không tự tạo socket/HTTP client; chỉ gọi transport được truyền vào.
- Thành phần phải có symbol/index_group/marketCode, không rỗng, không trùng và đúng nhóm/sàn.
- Chỉ nhận mã trong danh sách, giữ nhóm và sàn từ bootstrap; không tự suy ra nhóm từ tên mã.
- Ý định đăng ký gồm X, F, X-Quote, X-Trade, R, B cho danh sách mã.
  Đây không phải frame SignalR thực tế. Adapter live sau này phải xác minh cách SDK gộp/chuyển kênh;
  không giả định gọi SwitchChannels nhiều lần sẽ cộng dồn tất cả kênh.

Mã chính:

| Tệp | Vai trò |
|---|---|
| `src/ssi_api/stream_collector.py` | Interface, bộ điều phối, giới hạn, sink và ghép patch |
| `src/ssi_api/fake_stream.py` | Luồng kịch bản và đồng hồ ảo, không ngủ thời gian thật |
| `src/ssi_api/collect_sample.py` | Tạo kịch bản, SQLite và bảng bàn giao |
| `tests/test_ssi_stream_collector.py` | 27 kiểm thử collector/ghép/sink |

## 3. Quy tắc ghép

- Chỉ trường xuất hiện trong patch mới được cập nhật. Khóa vắng giữ cũ; null hoặc số sai đã được decoder chuyển None làm mất giá trị cũ.
- Mỗi trường giữ `field_updated_at`, `field_received_at`, `field_message_type`, `field_issues`.
  Một cập nhật Quote không làm mới đồng hồ ngoại hoặc giá mở cửa.
- Timestamp nguồn cũ không ghi đè trường có timestamp mới. Nó có thể bổ sung một trường trước đó chưa có;
  vì vậy từng trường có tuổi riêng để task 3 đánh giá, không coi cả hàng đều mới.
- Cùng timestamp nhưng giá trị khác: áp dụng thứ tự nhận, có tính xác định. Không khẳng định đó là thứ tự phát sinh tại sàn vì chưa có sequence được kiểm chứng.
- Thông điệp trùng dựa trên loại/source_at/payload đã chuẩn hóa; không dùng thời gian nhận để làm mới dữ liệu trùng.
  Bộ nhớ chống trùng giới hạn 4096 thông điệp mỗi kết nối, không hứa chống trùng toàn bộ lịch sử.
- Thiếu thời gian nguồn, ngày nguồn sai ngày kết nối hoặc timestamp vượt thời gian nhận hơn 5 giây thì không ghép.
  Mốc 5 giây là quy tắc phòng vệ của ứng dụng, cần xác minh đồng hồ thực tế; không phải cam kết từ SSI.
- Nếu ngày nhận thay đổi, session bị ngắt để bootstrap lại. Không ghép qua ngày bằng danh sách cũ.
- Phiên và trạng thái giữ ở từng mã. Không tạo marketSession của toàn sàn từ thông điệp F của một mã.
- Cờ ngoại ước tính được giữ. Giá trị ước tính giảm vẫn được cập nhật; task 3–4 sẽ có chính sách chất lượng/phương pháp riêng.

`fields_complete` chỉ nghĩa các trường cần thiết đã xuất hiện và khác null. Nó không chứng minh đúng giá,
độ mới, phiên đủ điều kiện hoặc đã xác minh đơn vị. Mọi trạng thái trong task 2 đều có **ranking_ready=False**.
HALT/ATC vẫn có thể đủ trường nhưng không được xem là sẵn sàng xếp hạng.

## 4. Ngắt/kết nối lại và giới hạn

- Mất kết nối: ghi disconnected, xóa baseline, chờ backoff rồi bootstrap và subscribe lại.
- Tối đa 3 lần kết nối lại theo mặc định; backoff 1, 2, 4 giây (được giới hạn bởi thời lượng còn lại).
- Không có dữ liệu đủ lâu theo idle_seconds thì cũng ngắt và thử lại. receive timeout tối đa 1 giây để kiểm tra thời lượng.
- Auth thất bại: ghi auth_failed và dừng, không tự retry đăng nhập.
- Dừng theo thời lượng hoặc số thông điệp tối đa; session được close cả khi sink ghi lỗi.
- Trạng thái trước gap không được trả về làm baseline hiện tại. Sau reconnect chỉ có Trade thì vẫn thiếu các trường khác.
- Nếu dừng bình thường, report giữ snapshot lịch sử cuối cùng, không tuyên bố kết nối còn sống.

Bản này dùng cơ chế pull tuần tự để tạo backpressure; không có queue producer không giới hạn.
Chưa triển khai SDK callback, queue đa luồng, batch insert hoặc quota HTTP: các phần đó cần đúng adapter/khối lượng thực tế.
Transport live về sau phải chuyển lỗi mất kết nối/auth thành loại lỗi interface tương ứng và tuân thủ timeout.

## 5. Dữ liệu được ghi và phạm vi của task 3

Dùng EventStore hiện có, thêm hai loại bản ghi để giữ provenance:

| Channel | Nội dung |
|---|---|
| connection | Vòng đời, epoch và lý do loại/an toàn; không ghi thông báo ngoại lệ tùy ý |
| universe | Thành phần mỗi lần bootstrap |
| ssiRaw | Chỉ các trường thị trường mà decoder đã dùng, giữ tên trường nguồn |
| ssiDecoded | Kết quả decoder đầy đủ: source_at, received_at, present_fields, issues |
| ssiMerged | Snapshot từng mã cùng field clocks, nhóm và epoch |

`ssiRaw` là bản lọc, không phải bản sao byte gốc. Khóa không dùng bị bỏ; giá trị số không hữu hạn/kiểu sai được chuyển null
để ghi SQLite JSON an toàn. Body JSON lỗi không được lưu tùy ý, chỉ ghi trạng thái decode_error.
Không lưu token, credential hoặc nội dung auth vào các record này.

Không chuyển chúng thành stockInfo của pipeline replay cũ vì pipeline đó chưa giữ đủ metadata SSI.
Đây chỉ là điểm nối lưu trữ tối thiểu của collector. **Task 3** mới xây replay/đánh giá chất lượng cho các record này,
đo độ phủ, nhận biết gap và thiết kế kho hiệu quả hơn. UI/xếp hạng đang có không tự chuyển sang dùng kho task 2.

## 6. Kiểm thử và giới hạn bàn giao

**27 kiểm thử riêng task 2 đạt. Toàn bộ dự án: 150 kiểm thử đạt trong 8,00 giây.**

Đã kiểm tra: patch/null/field clocks, dữ liệu cũ và trùng, snapshot đủ/thiếu, per-symbol status,
ngoại ước tính giảm, ngoài danh sách/sai sàn/sai ngày/thiếu timestamp, reconnect/rebootstrap/resubscribe,
bootstrap không hợp lệ, auth fail, idle và retry limit/backoff, thời lượng/số gói, sink lỗi vẫn đóng session,
SQLite giữ provenance, số NaN không làm hỏng sink và không ghi khóa lạ nhạy cảm trong mẫu.

Chưa dùng SSI thật, chưa kiểm chứng scope/SDK/wire format/quota/độ trễ hoặc chất lượng dự báo.
Không thay đổi các công thức chấm điểm hoặc giao diện trong task này.

**Trạng thái:** task 2 hoàn thành offline. Cập nhật sau bàn giao: [task 3](TASK_3_LUU_TRU_REPLAY_CHAT_LUONG.md) đã có ghi lô, replay và chất lượng dữ liệu; các giới hạn mô tả trên là phạm vi task 2 tại thời điểm bàn giao.
