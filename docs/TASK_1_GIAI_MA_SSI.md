# Task 1 — Bộ giải mã dữ liệu SSI

Hoàn thành: **04/11/2026**, chờ người học kiểm tra. Chỉ thực hiện task 1 trong chuỗi bảy task.

## Kết quả

- `src/ssi_api/decoder.py`: hàm `decode_fcdata(...)`, không kết nối mạng và không giữ trạng thái lần gọi trước.
- Hỗ trợ hợp đồng **FCData v2**: F, X, X-QUOTE, X-TRADE, R và B.
- Nhận object Python, chuỗi JSON hoặc bytes UTF-8. Envelope DataType/Content có Content dạng object hoặc chuỗi JSON;
  hỗ trợ payload độc lập nếu có RType/DataType.
- Chuyển chuỗi số thành số; thiếu trường giữ vắng, null giữ None. Số âm/NaN/Infinity/bool hoặc kiểu sai được gắn lỗi trường.
- Giữ giá ATO/ATC, ba mức chào đầu và khối lượng bằng 0 thật; không tự điền mức chào còn thiếu.
- Tách LastVol/Volume phát sinh khỏi TotalVol cộng dồn. Value của B không biến thành tổng thanh khoản.
- Ưu tiên LastPrice cho giá khớp trong X; Close lưu riêng, không tự thay thế khi LastPrice vắng.
- Ánh xạ N→NORMAL, H→HALT; phiên lạ không đổi sang LO. Mã/sàn thiếu hoặc mâu thuẫn có lỗi rõ ràng.
- Tách source_at và received_at; không suy ra ngày nguồn từ ngày nhận khi thiếu ngày nguồn.
- Giữ field_updated_at cho các trường đã ánh xạ và present_fields cho việc ghép patch ở task sau.
- Ghi cờ ngoại HOSE ước tính theo tài liệu R; với sàn khác, cờ None nghĩa là chưa có kết luận, không khẳng định chính xác.
- Từ chối envelope/JSON sai, khóa lặp, alias mâu thuẫn hoặc profile/type chưa hỗ trợ; lỗi không in payload/giá trị bí mật.

Căn cứ: [FCData streaming](https://guide.ssi.com.vn/ssi-products/fastconnect-data/streaming-data).
Các quy tắc phát hiện lỗi và cách giữ provenance là quyết định triển khai của dự án, không phải đặc tính được SSI bảo đảm.

## Cách kiểm tra đơn giản

Mở [bảng kết quả mẫu](../evidence/task1/KET_QUA_MAU.md).
Bảng có sáu thông điệp tự tạo và danh sách những điểm cần xem bên dưới.

- [Đầu vào JSON giả lập](../evidence/task1/ssi_synthetic_input.json).
- [Đầu ra đã giải mã](../evidence/task1/ssi_decoded_output.json).
- [Báo cáo kiểm thử](../evidence/task1-tests.xml).

Có thể tạo lại mẫu, hoàn toàn offline:

```powershell
& "$HOME\.venv\Scripts\Activate.ps1"
python -X utf8 -m src.ssi_api.decode_sample
```

Mẫu dùng DEMO01/HNDEMO01 hư cấu. `source=synthetic` được truyền rõ ràng vào decoder.
Không cần khóa SSI, không đọc .env và không tự gọi API khi tạo mẫu.

## Hợp đồng hàm cho task 2

```python
result = decode_fcdata(
    message,
    received_at="2026-11-04T10:00:01+07:00",
    source="synthetic",  # dùng ssi cho dữ liệu SSI thật
    profile="fcdata_v2",
)
```

| Khóa đầu ra | Ý nghĩa |
|---|---|
| schema_version | Phiên bản hợp đồng nội bộ: ssi-fcdata-v2-patch-1 |
| source / profile / message_type | Nguồn, phiên bản dịch vụ và loại thông điệp |
| channel | stockInfo: patch cho từng mã, không phải trạng thái cả sàn |
| payload | Các trường đã chuyển; chỉ những trường có mặt/được giải mã |
| source_at | Thời gian nguồn có UTC+7; None nếu không đủ căn cứ |
| received_at | Thời gian do bộ nhận cung cấp, bắt buộc có timezone |
| field_updated_at | Thời gian nguồn cho trường được ánh xạ; None nếu thiếu timestamp |
| present_fields | Phân biệt khóa vắng với khóa có giá trị null |
| field_sources | Alias nguồn thực sự dùng cho từng trường |
| issues | Mã vấn đề và tên trường, không chứa giá trị lỗi tùy ý |
| metadata | Đơn vị còn cần kiểm chứng, cờ ước tính và danh sách trường cộng dồn |

`book_levels=3` là phạm vi chuẩn hóa của phương pháp, không chứng minh thông điệp đã có đủ ba mức.
Decoder không tự suy ra thành phần VN30 từ mã; danh sách nhóm do bước bootstrap cung cấp.
Không có source_at hoặc có issues không mặc định đồng nghĩa đủ điều kiện chấm điểm;
collector/chất lượng dữ liệu cần chính sách xử lý tương ứng trong task 2–3.

F trả patch trạng thái **từng mã**, không phát sinh marketSession cho toàn sàn: tránh một mã tạm dừng làm cả sàn bị coi tạm dừng.
Các record đã giải mã chưa phải tham số hoàn chỉnh cho EventStore.append; task 2 sẽ gắn run, lưu raw và nối pipeline.

## Phạm vi còn lại

- Chưa triển khai collector hoặc ghép các patch thành trạng thái đầy đủ; thuộc task 2.
- Chưa thay chính sách stale/rollback của pipeline cũ; thuộc task 3–4. Không đưa patch này vào xếp hạng thật trước khi tích hợp các bước đó.
- Chưa có dữ liệu SSI thật để kiểm chứng schema/đơn vị. Price unit mới ghi theo tài liệu; volume vẫn ghi chờ xác minh.
- Decoder này không nhận giao thức V3, MI, lô lẻ hoặc dữ liệu giao dịch tài khoản; chưa suy đoán map khi không có hợp đồng.
- Không cài SDK hay mở kết nối mạng trong task 1.

## Kiểm thử

**52 kiểm thử riêng decoder đạt. Toàn bộ dự án: 123 kiểm thử đạt trong 11,00 giây.**

Các nhóm kiểm tra: envelope/UTF-8/JSON, sáu loại thông điệp, số/null/thiếu, số lặp/mâu thuẫn,
khối lượng phát sinh/cộng dồn, ba mức/ATO/ATC, alias khối ngoại và cờ ước tính,
trạng thái, thời gian nguồn, profile không hỗ trợ, không đổi input hoặc giữ dữ liệu cũ.

Không thay các kết quả này bằng bằng chứng nghiệm thu dữ liệu SSI thật.

**Trạng thái bàn giao:** task 1 hoàn thành phần offline; chờ người học kiểm tra. Chưa bắt đầu task 2.
