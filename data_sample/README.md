# Dữ liệu mẫu P2

`synthetic_quotes.csv` chứa **12 quan sát tự tạo**, bốn mã hư cấu DEMO01–DEMO04
tại ba mốc ngày 23/10/2026, UTC+7. Không lấy từ NEO, không phải danh sách VN30,
không phải kết quả thị trường và không dùng làm bằng chứng tài chính trong bài nộp.

- `source`: luôn là `synthetic`.
- `observed_at`: thời điểm giả lập có offset +07:00, không phải giờ cập nhật trực tiếp.
- `symbol`: mã hư cấu DEMOxx.
- `price_vnd`: giá giả lập, VNĐ.
- `volume_shares`: khối lượng giả lập lũy kế, cổ phiếu.
- `turnover_vnd`: giá trị giao dịch giả lập lũy kế, VNĐ.
- `foreign_buy_vnd`, `foreign_sell_vnd`: giá trị mua/bán nước ngoài giả lập lũy kế, VNĐ.

Tên cột là schema nội bộ cho fixture P2, **không phải cam kết schema API NEO**.
Sổ lệnh, quy tắc chuẩn hóa dữ liệu NEO, công thức bốn yếu tố và xếp hạng sẽ được
thực hiện ở các giai đoạn sau. Không thay fixture này bằng dữ liệu thật mà vẫn giữ nhãn synthetic.

