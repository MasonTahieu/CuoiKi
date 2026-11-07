# Task 3 — Lưu trữ, replay và chất lượng dữ liệu

Ngày thực hiện: **04/11/2026**. Hoàn thành với dữ liệu giả lập; chưa gọi SSI thật.
Phạm vi task này là nhật ký của collector task 2 và kiểm tra dữ liệu trước khi tính điểm.
Chưa chuyển sang task 4 hoặc thay đổi giao diện/công thức.

Xem trước [kết quả mẫu có tám mốc kiểm tra](../evidence/task3/KET_QUA_MAU.md).

## 1. Đã làm

- Ghi SQLite theo lô, giao dịch nguyên khối; giới hạn bộ đệm và flush tại các mốc kết nối.
- Đọc kho ở chế độ chỉ đọc, chọn source/run và giữ một ảnh chụp nhất quán trong suốt lượt đọc.
- Tái tạo trạng thái từ `ssiDecoded`, theo thứ tự event ID; không lấy snapshot cache làm dữ liệu quyết định.
- Chọn mốc thời gian có múi giờ, thêm event ID khi cần phân biệt các sự kiện cùng giây.
- Kiểm tra từng trường: thiếu, null, lỗi số, dấu thời gian, quá cũ và chênh nguồn–nhận.
- Thống kê độ phủ riêng hai nhóm, khoảng mất kết nối, thông điệp trùng/cũ và counter giảm.
- Xuất snapshot, chất lượng từng trường, gap và manifest để đối chiếu.

## 2. Các phần đã thêm

| Tệp | Vai trò |
|---|---|
| `src/data/store.py` | Giữ schema cũ; thêm `append_many`, rollback toàn lô nếu lỗi |
| `src/data/ssi_journal.py` | `BufferedSink` và trình đọc SSIJournal chỉ đọc |
| `src/data/ssi_quality.py` | Chính sách chất lượng và độ phủ từng nhóm/trường |
| `src/ssi_api/replay.py` | Dựng lại một run, xuất báo cáo và lệnh chạy cục bộ |
| `src/ssi_api/replay_sample.py` | Tự tạo SQLite giả lập và các mốc để người học kiểm tra |
| `tests/test_ssi_replay_quality.py` | Kiểm thử lưu theo lô, phát lại, chất lượng và xuất tệp |

Không cần cài thêm thư viện. Dùng Python và môi trường hiện có.

## 3. Quy tắc lưu và độ bền dữ liệu

Mỗi event có ID tăng theo thứ tự ghi, source, run, received_at, channel, payload và fingerprint.
Giữ các channel của task 2: connection, universe, ssiRaw, ssiDecoded, ssiMerged.
Không đọc `.env`, không gọi mạng và không lưu thông tin đăng nhập trong bước này.

`append_many` dùng một transaction cho cả lô; một event không hợp lệ làm rollback toàn lô.
Fingerprint tránh ghi lặp một event giống hệt. Nó không thay thế bộ chống trùng thông điệp thị trường trong PatchState.

`BufferedSink` mặc định tối đa 128 event mỗi lô, cho phép cấu hình 1–10.000.
Khi đầy hoặc gặp connecting/connected/disconnected/auth_failed/stopped thì flush.
Chủ sở hữu sink phải gọi `flush()` trước khi đóng store; mẫu task 3 đã làm việc này.
Nếu ghi lỗi, sink giữ phần đang chờ và báo lỗi; collector dừng thay vì báo thành công giả.
Nếu tiến trình bị tắt đột ngột, các event còn trong RAM chưa flush có thể mất.
Chưa có queue callback đa luồng, đo tải thật hoặc cơ chế ghi bền sau mỗi thông điệp.

## 4. Hợp đồng phát lại

1. Chọn đúng một run; run phải có đúng một source `synthetic` hoặc `ssi`. Run trộn nguồn bị từ chối.
2. Chỉ đọc file đã có, không tạo SQLite trống khi sai đường dẫn. Các bản ghi được đọc theo lô trong một read transaction.
3. Duyệt theo ID ghi; chỉ nhận event có received_at không sau mốc và cùng ngày địa phương +07:00.
4. Dữ liệu có source_at sau mốc cũng chưa được đưa vào trạng thái. Thiếu source_at không được suy ra từ thời gian nhận.
5. Mỗi epoch kết nối có danh sách bootstrap riêng. Gap/auth fail xóa baseline; dữ liệu mới không ghép với dữ liệu trước gap.
6. Cập nhật từng trường bằng source_at, giữ nguyên quy tắc null/patch và chống trùng của collector task 2.
7. Khi cùng source timestamp, áp dụng thứ tự đến trong journal. Chưa có sequence ID từ SSI để giải quyết chi tiết hơn.
8. Sau stopped, giữ dữ liệu để xem lịch sử nhưng không coi kết nối còn hoạt động.

`ssiRaw` và `ssiMerged` được đếm để đối chiếu, không dùng dựng trạng thái.
JSON hỏng hoặc hợp đồng decoded mâu thuẫn làm dừng phát lại; không xuất một báo cáo một phần như thể thành công.
`--event-id` giới hạn đến đúng event thuộc run; nếu không nhập `--as-of`, dùng thời gian nhận của event đó.
Nếu chỉ nhập thời gian, tất cả event cùng thời gian không vượt mốc đều được xét.
Mặc định không chọn run sẽ lấy run collector được ghi gần nhất, kể cả run chỉ mới bắt đầu kết nối.

Lệnh này dành riêng cho journal SSI mới. `src.cli replay` và UI cũ chưa được nối sang nó; phần tích hợp đến sau.

## 5. Chính sách chất lượng mặc định

| Kiểm tra | Quy tắc hiện tại |
|---|---|
| Trường bắt buộc | Giá cuối, mở cửa, tổng giá trị khớp, giá trị ngoại mua/bán, giá và khối lượng bid/ask ba mức, phiên và trạng thái mã |
| Thiếu/null | Giữ thiếu, không điền 0 hoặc dùng lại giá trị trước null |
| Lỗi số | Giá/khối lượng không hữu hạn hoặc âm được decoder đánh dấu; số sai thành null nhưng vẫn giữ `INVALID_NUMBER` |
| Giá trị hợp lệ | Trường giá phải lớn hơn 0; khối lượng và giá trị cho phép 0; giá ATO/ATC không dùng như giá số trong phiên LO |
| Độ mới trường động | Cả tuổi nguồn và tuổi nhận không vượt 60 giây, phải cùng ngày |
| Mở cửa/phiên/trạng thái | Giữ trong cùng ngày và epoch; chưa áp ngưỡng 60 giây vì không nhất thiết phát lại mỗi quote |
| Chênh nguồn–nhận | Chặn nếu nhận sau nguồn quá 10 giây, hoặc nguồn đi trước nhận quá 5 giây |
| Phiên/trạng thái | Chỉ qua kiểm tra khi LO và NORMAL; HALT là trạng thái từng mã |
| Kết nối | Phải có bản ghi connected hiện hành và baseline của epoch đó |
| Counter giảm | Chặn nếu tổng khối lượng/giá trị khớp hoặc khối lượng ngoại lũy kế giảm trong cùng epoch |
| Giá trị ngoại ước tính | Giữ cờ cảnh báo; không ép ngoại mua/bán theo giá trị phải tăng đơn điệu |

Các ngưỡng 60/10/5 giây là quy ước thử nghiệm của dự án, chưa được xác minh bằng SSI thật.
Có thể truyền `QualityPolicy` khác khi gọi Python; decoder/collector vẫn giữ giới hạn nguồn đi trước thời gian nhận 5 giây.
Quy tắc giữ phiên/trạng thái trong ngày cần đối chiếu tần suất thông điệp F thực tế trước khi dùng live.

- `source_age_seconds = as_of - source_at`.
- `receive_age_seconds = as_of - received_at` của chính trường đó.
- `recorded_lag_seconds = received_at - source_at`.

Chênh nguồn–nhận có thể chứa lệch đồng hồ và thời gian xử lý; không phải đo độ trễ mạng thuần túy.
Một quote mới chỉ làm mới các trường nó có. Khối ngoại vẫn có thể quá cũ trong khi bid mới.
Counter giảm giữ cờ cho đến khi có bootstrap/epoch mới; một bản ghi phục hồi đơn lẻ chưa tự xóa nghi vấn đó.

`fields_complete` chỉ nói đủ giá trị khác null. `data_usable` nói qua các kiểm tra dữ liệu tại mốc chọn.
`ranking_ready` luôn **false**: task 4 còn phải kiểm chứng phương pháp, ngữ nghĩa và cỡ nhóm.
Hai mã mẫu không đạt số lượng tối thiểu 10 mã/nhóm của hệ thống xếp hạng.

## 6. Ý nghĩa báo cáo

Độ phủ tính trên danh sách bootstrap tại mốc chọn: số mã, số mã đủ trường, số mã qua kiểm tra;
mỗi trường có present/fresh_valid/total. Mã HALT có thể đủ mọi trường nhưng không dùng được.
Độ phủ này không chứng minh đã có đầy đủ 30 mã thật hoặc đo được tỷ lệ giao dịch đã nhận.

Gap tính từ marker disconnected/auth_failed đến connected tiếp theo, hoặc đến mốc chọn nếu còn mở.
Đây là khoảng mất kết nối **được journal ghi nhận**, không xác định chính xác số giao dịch bị thiếu.
Khoảng connected cũng chỉ phản ánh marker đã ghi, không chứng minh kết nối đang sống khi tiến trình đã chết.
Sau gap có thể connected nhưng vẫn chưa đủ baseline; báo cáo phân biệt hai trường hợp này.

| Tệp xuất | Nội dung |
|---|---|
| `snapshot.csv` | Source/run/as_of, nhóm/mã, giá trị thô, kết quả chất lượng, lý do và cảnh báo |
| `field_quality.csv` | Trường bắt buộc kể cả chưa từng nhận; thời gian, tuổi, loại thông điệp và lỗi trường |
| `gaps.csv` | Bắt đầu/kết thúc, thời lượng, gap đang mở |
| `quality.json` | Toàn bộ báo cáo, ngưỡng chính sách và provenance |
| `manifest.json` | Source/run/as_of, chính sách và SHA-256 của bốn tệp trên |

Trong CSV từng trường, tuổi/chất lượng được đánh giá cho các trường bắt buộc; trường tùy chọn chỉ kèm dấu thời gian và nguồn thông điệp.
Manifest giúp phát hiện thay đổi nội dung, không xác thực nguồn dữ liệu như chữ ký của SSI.
Chạy lại với cùng thư mục xuất ghi đè các tệp báo cáo; nếu hệ điều hành báo lỗi giữa chừng, cần chạy lại và kiểm tra manifest.
Journal gốc không bị sửa bởi replay/export.

## 7. Cách tái tạo

Các lệnh chạy tại thư mục dự án `neo-vn30-screener`:

```powershell
& "$HOME\.venv\Scripts\Activate.ps1"
python -X utf8 -m src.ssi_api.replay_sample
python -X utf8 -m src.ssi_api.replay --db runtime/task3-synthetic.sqlite --list-runs
```

Chọn run thứ nhất trong danh sách `runs` mà lệnh tạo mẫu trả về để xem kịch bản mất kết nối:

```powershell
python -X utf8 -m src.ssi_api.replay --db runtime/task3-synthetic.sqlite --run "RUN_DA_CHON" --as-of "2026-11-04T10:00:13+07:00" --out runtime/replay-kiem-tra
```

`RUN_DA_CHON` là run ID để thay vào, không phải giá trị API. Chọn `--event-id` khi muốn dừng giữa các event cùng giây.
Mẫu tạo SQLite riêng tại runtime/task3-synthetic.sqlite; mỗi lần chạy thêm hai run riêng, không trộn với kho SSI thật.
Báo cáo mẫu nằm trong [evidence/task3](../evidence/task3/KET_QUA_MAU.md).

## 8. Nghiệm thu và phần còn lại

**31 kiểm thử riêng task 3 đạt; toàn bộ dự án 181 kiểm thử đạt.**
Bằng chứng: [kết quả pytest](../evidence/task3-tests.xml). Đã chạy lệnh tạo mẫu, liệt kê run và xuất replay từ CLI.

Kiểm thử riêng task 3 bao gồm: transaction rollback, idempotence, flush/buffer lỗi;
chọn run/cursor, read snapshot khi có writer, deterministic replay, dữ liệu tương lai/cũ/trùng,
khác ngày, mất kết nối và auth fail, null/số sai, dữ liệu ngoại cũ dù quote mới,
HALT từng mã, counter/ngoại ước tính và xuất manifest.

Chưa kiểm chứng đơn vị/phiên/độ trễ với SSI, chưa nối adapter streaming thật hoặc đo khả năng chịu tải.
Task 4 tiếp theo là kiểm chứng bốn yếu tố khi người học yêu cầu; task 5 mới hoàn thiện giao diện.

**Trạng thái: task 3 hoàn thành offline, chờ người học kiểm tra.**
