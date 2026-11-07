# Task 6 — Kiểm thử toàn tuyến SSI

Luồng kiểm thử đi từ gói tin FCData v2 giả lập qua decoder, collector, nhật ký SQLite, phát lại, kiểm tra chất lượng, bốn yếu tố, xếp hạng, giao diện Streamlit và CSV. Dữ liệu gồm 22 mã hư cấu, 11 mã mỗi nhóm. Các phản hồi REST và lỗi kết nối được mô phỏng trong bộ kiểm thử.

## Kết quả

- **95 thông điệp** được đưa vào collector. Có 94 gói giải mã được và 92 lần cập nhật trạng thái. Ba gói còn lại lần lượt là gói trùng, gói cũ bị bỏ và loại thông điệp chưa hỗ trợ.
- Ở mốc đủ dữ liệu, HOSETEST11 có điểm yếu tố **100/0/100/20**, tổng **55**, hạng **4**. Lọc bảng còn một mã giữ nguyên điểm, hạng và tập mã dùng để tính. Đổi trọng số sang 40/20/20/20 cho **64 điểm, hạng 1** và mã cấu hình khác.
- Khi hai mã VN30 thiếu một mức khối lượng chào mua, VN30 còn **9 mã hợp lệ** và dừng xếp hạng. HNX30 vẫn xếp hạng **11 mã**. Sau mất kết nối, chỉ một bản cập nhật giá chưa đủ để xếp hạng. Khi nhận lại đầy đủ dữ liệu nền, cả hai nhóm khôi phục điểm và hạng trước đó.
- Giao diện hiện xác thực thất bại ở đúng mốc mô phỏng token hết hạn và chặn điểm từ dữ liệu cũ. CSV có nguồn, lần thu thập, mốc, ID sự kiện, nhóm, tập mã, phương pháp và trọng số.
- Bản sao mã nguồn ở thư mục mới chạy được kiểm tra cấu hình, lệnh demo xếp hạng 24 mã và cả hai màn hình demo. Bản sao dùng môi trường Python hiện có và bắt đầu với kho trống, khóa API trống.

## Đối chiếu ma trận gốc

T01–T23 có bằng chứng kiểm thử offline. T24 đã chạy thử mã nguồn tại đường dẫn mới. Kiểm tra chính gói nộp thực hiện khi có gói ở task 7. [Ma trận gốc, mục 8](../../KE_HOACH_BO_LOC_VN30_DA_YEU_TO.md)

| Mã | Kết quả đối chiếu | Bằng chứng |
|---|---|---|
| T01 | Giá 100 → 102 cho động lượng 2%. | A |
| T02 | Bid 99, ask 101 cho spread 200 bps. | A |
| T03 | Mua 600, bán 400 cho mất cân bằng 0,2. | A |
| T04 | Ngoại mua 30, bán 10, tổng 200 cho ròng 20 và tỷ lệ 0,1. | A |
| T05 | Tổng giá nhân khối lượng sáu mức là 99.700. | A |
| T06 | Giá mở cửa hoặc giá trị khớp bằng 0 làm mã bị loại. | B |
| T07 | Null ở một mức sổ lệnh làm mã thiếu dữ liệu. Trường không xuất hiện trong cập nhật giữ giá trị và dấu thời gian cũ. | A, C |
| T08 | ATO/ATC giữ nhãn ở bước giải mã và bị loại khi cần giá số. | B, D |
| T09 | Ba giá trị tăng dần cho phân vị 0, 50, 100. | A |
| T10 | Nhóm đồng giá trị nhận 50 điểm phân vị. | A, B |
| T11 | VN30 còn 9 mã thì dừng xếp hạng và hiện lý do. HNX30 đủ 11 mã vẫn có hạng. | A |
| T12 | Mã thiếu yếu tố có hạng và tổng điểm trống. | A, B |
| T13 | Điểm 80/60/40/20 với trọng số đều cho tổng 50. | A |
| T14 | Lọc hiển thị một mã giữ nguyên điểm, hạng và tập mã so sánh. | A |
| T15 | Đổi trọng số tạo mã cấu hình khác và giữ mã tập so sánh. | A |
| T16 | Hai mã đồng điểm cùng hạng 1 và được sắp theo tên mã để hiển thị ổn định. | A |
| T17 | Gói trùng, gói đến muộn và cập nhật null được xử lý qua journal đến giao diện. | A, C |
| T18 | Qua ngày phải lấy lại dữ liệu nền. Ca ngoài phiên LO bị chặn. | B, C, E |
| T19 | Hai bản ghi giá trị khớp lũy kế 100 triệu giữ giá trị 100 triệu. Bản ghi mới đổi giờ nhận và bản ghi ngoại trùng giữ giờ nhận cũ. | A, D |
| T20 | Mất kết nối, lỗi adapter và hết hạn xác thực xóa trạng thái nền hiện hành. HTTP 401 yêu cầu xác thực lại trước lần đọc tiếp theo. | A, F |
| T21 | Mỗi ca 429/503/403 và timeout dừng sau một lần đọc đã được giãn nhịp. | F |
| T22 | Phát lại cùng kho, ID sự kiện và cấu hình cho cùng báo cáo, điểm và hạng. | A, E |
| T23 | Tập mã VN30 chuyển 11 → 9 làm thay đổi `cohort_id`. CSV giữ mã tập so sánh và lý do loại. | A |
| T24 | Đạt kiểm tra mã nguồn ở vị trí mới. Kiểm tra gói nộp sau khi đóng gói. | Chạy thử bản sao cục bộ |

- A — Luồng từ gói SSI đến giao diện và phép tính tay. [test_task6_integration.py](../tests/test_task6_integration.py)
- B — Chuẩn hóa, phiên giao dịch và kiểm thử công thức nền. [test_pipeline.py](../tests/test_pipeline.py)
- C — Collector, ghép từng trường và chuyển ngày. [test_ssi_stream_collector.py](../tests/test_ssi_stream_collector.py)
- D — Giải mã các trường thị trường. [test_ssi_decoder.py](../tests/test_ssi_decoder.py)
- E — Phát lại SQLite, độ mới và kết quả xác định. [test_ssi_replay_quality.py](../tests/test_ssi_replay_quality.py)
- F — Lỗi REST giả lập và chặn chấm điểm dữ liệu ngày trên UI. [test_ssi_rest_failures.py](../tests/test_ssi_rest_failures.py)

## Lỗi tìm thấy và xử lý

| Tình huống | Sau khi sửa |
|---|---|
| Ngoại lệ bất ngờ ở bước chuẩn bị, mở, đăng ký hoặc nhận dữ liệu của adapter | Collector ghi `adapter_error`, dừng và xóa trạng thái nền hiện hành. Replay và UI hiển thị lỗi kết nối. Nhật ký không chứa nội dung ngoại lệ. |
| Danh sách REST chứa bản ghi sai kiểu | REST báo lỗi hợp đồng trước khi đọc các trường của bản ghi. |
| REST trả HTTP 401 | Client bỏ token trong phiên và yêu cầu xác thực lại. Lần đọc kế tiếp bị chặn trước khi gửi cho đến khi xác thực thành công. |

Ca REST theo ngày dùng 20 mã và bật cờ xác minh để kiểm riêng ràng buộc dữ liệu. Cả hai nhóm vẫn để trống hạng vì thiếu sổ lệnh intraday. HTTP 429, 503, 403, timeout và schema lỗi được kiểm qua phản hồi giả lập. Chính sách hiện tại giãn nhịp yêu cầu và dừng khi gặp lỗi để tránh gửi dồn.

## Chạy lại

```powershell
& "$HOME\.venv\Scripts\Activate.ps1"
python -m pytest -q tests/test_task6_integration.py tests/test_ssi_rest_failures.py
python -m pytest -q --junitxml=evidence/task6-tests.xml
```

13 ca mới đạt, toàn dự án **209 kiểm thử đạt**. [Kết quả pytest](../evidence/task6-tests.xml)

Nghiệm thu trực tiếp vẫn cần quyền SSI, adapter streaming đúng phiên bản được cấp và dữ liệu nhiều phiên để đối chiếu đơn vị, quota, cơ chế làm mới token, độ trễ và độ phủ. Mức đổi hạng trên dữ liệu giả lập dùng để kiểm tra hành vi phần mềm.
