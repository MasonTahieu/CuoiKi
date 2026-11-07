# Kiểm chứng ngoài mẫu: điểm cuối ngày và lợi suất phiên sau

Dữ liệu SSI thật, rổ VN30, **15 phiên**, 14 cặp phiên liên tiếp. Trọng số cố định từ trước, không dò trên dữ liệu này. Điểm phiên t chỉ dùng dữ liệu phiên t.
Lợi suất phiên sau: priceChangePercent của phiên t+1 (so với giá tham chiếu), nên ngày giao dịch không hưởng quyền không làm méo kết quả.

| Cấu hình | IC trung bình | Độ lệch chuẩn | t | Tỷ lệ cặp IC > 0 | Top 5 − Bottom 5 (điểm %) | t |
|---|---:|---:|---:|---:|---:|---:|
| Cân bằng 33/33/33 | -0,024 | 0,224 | -0,40 | 50% | -0,17 | -0,62 |
| Ưu tiên động lượng 50/25/25 | -0,017 | 0,222 | -0,29 | 50% | -0,04 | -0,15 |

## IC của từng yếu tố (cấu hình cân bằng)

| Yếu tố | IC trung bình | t |
|---|---:|---:|
| Động lượng | -0,016 | -0,30 |
| Thanh khoản | +0,038 | +1,12 |
| Dòng tiền ngoại | -0,065 | -1,17 |

## Kết luận

Không có bằng chứng điểm dự báo lợi suất phiên sau (IC trung bình -0,024, t = -0,40, 14 cặp phiên). Điểm dùng để thu hẹp danh sách, không phải tín hiệu mua bán.

- IC là hệ số tương quan hạng Spearman giữa điểm phiên t và lợi suất phiên t+1 của các mã được xếp hạng.
- |t| < 2 nghĩa là chưa phân biệt được với 0. Với khoảng 14 cặp phiên, phép thử có độ nhạy thấp.
- Kết quả này không thay đổi cách chấm điểm. Sản phẩm không trình bày điểm như xác suất tăng giá.

Chi tiết từng cặp phiên: [kiem_chung_ngoai_mau.csv](kiem_chung_ngoai_mau.csv). Tạo lại: `python -X utf8 -m src.cli evaluate-v3`.
