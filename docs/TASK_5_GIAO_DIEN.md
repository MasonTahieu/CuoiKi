# Task 5 — Giao diện bảng điểm và phát lại SSI

## Mở demo

Chạy `RUN_APP.ps1` tại thư mục dự án. Cấu hình mặc định `APP_MODE=demo`, `DATA_PROVIDER=ssi` có hai lựa chọn ở mục **Dữ liệu minh họa**.

- **Bảng điểm giả lập** có 12 mã VN30 hư cấu. Đổi trọng số, lọc mã và xem điểm từng yếu tố. Bộ lọc áp dụng sau khi tính hạng trong cả nhóm.
- **Nhật ký SSI mẫu** dựng hai lần thu thập giả lập trong kho tạm của phiên chạy ứng dụng. Mẫu dùng hai mã để minh họa chất lượng dữ liệu và ngưỡng tối thiểu 10 mã của mỗi nhóm.

| Tình huống mẫu | Thao tác và kết quả |
|---|---|
| Mất kết nối | Chọn lần **Mất kết nối và phục hồi** và mốc **10:00:06 · Mất kết nối**. Giao diện hiện trạng thái gián đoạn và chờ snapshot. |
| Phục hồi | Chọn mốc **10:00:13 · Dữ liệu cổ phiếu**. Lần kết nối thứ hai có dữ liệu mới và tab chất lượng hiển thị khoảng gián đoạn đã đóng. |
| Tạm ngừng một mã | Ở mốc **10:00:14 · Dữ liệu cổ phiếu**, xem mã DEMO02 ở trạng thái HALT và lý do chưa xếp hạng. Mốc **Đã dừng thu thập** cùng giây có số thứ tự riêng. |
| Dữ liệu cũ | Chọn lần **Dữ liệu khối ngoại cũ** rồi mở tab **Chất lượng dữ liệu**. Mốc mặc định 10:01:03 hiện khối ngoại 63 giây tuổi, cờ ước tính ở mã HOSE và lý do “Trường quá cũ”. |

Trong tab chất lượng, tuổi theo cụm là tuổi nguồn lớn nhất trong những trường của cụm. Mở **Xem dấu thời gian từng trường** để xem giờ nguồn, giờ nhận và cờ thiếu/cũ. Trạng thái kết nối phản ánh bản ghi SQLite tại mốc đang xem.

## Kho đã thu thập và tệp xuất

Với `APP_MODE=replay`, `DATA_PROVIDER=ssi` và `SSI_DATABASE` trỏ tới kho journal, chọn **Lần thu thập** rồi chọn một trong 200 mốc gần nhất của lần đó. ID sự kiện phân biệt bản ghi cùng giây. Với `APP_MODE=live`, giao diện đọc kho theo thời điểm hiện tại. Có nút **Đọc lại kho dữ liệu** và tùy chọn đọc lại mỗi 10 hoặc 30 giây, mặc định tắt.

Nút **Tải bảng đang xem (CSV)** giữ dữ liệu theo bộ lọc đang dùng và ghi kèm nguồn, lần thu thập, mốc phân tích, nhóm, phương pháp, tập mã và trọng số. Dữ liệu từ journal có thêm ID sự kiện và cờ ước tính giá trị ngoại. Tab **Phương pháp** cho xem mã cấu hình và tập mã dùng để tính điểm.

Kiểm chứng trên trình duyệt cục bộ đã thấy trạng thái mất kết nối, tuổi khối ngoại 63 giây và tự đọc lại bản ghi kết nối khi bật chu kỳ 10 giây. Kiểm thử giao diện cũng kiểm tra tệp CSV, nút đọc lại và ranh giới giữa kho giả lập và chế độ live. Toàn dự án đạt **196 kiểm thử**. [Kết quả pytest](../evidence/task5-tests.xml)

Giai đoạn này kiểm chứng bằng kho giả lập và bản ghi kết nối kiểm thử. Phần nghiệm thu nguồn SSI thật phụ thuộc quyền API và xác minh đơn vị dữ liệu.
