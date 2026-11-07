# Vì sao phạm vi chỉ gồm VN30

Dữ liệu SSI FastConnect V3 thật, REST `securitiesSummary` từng mã, **15 phiên** từ 2026-10-19 đến 2026-11-06.
Số liệu được lưu trước khi gỡ các dòng HNX30 khỏi kho dữ liệu ngày (07/11/2026).

| Chỉ tiêu | VN30 | HNX30 |
|---|---:|---:|
| Tổng giá trị khớp mỗi phiên (tỷ đồng) | 7.108 | 603 |
| Giá trị khớp trung vị một mã một phiên (tỷ đồng) | 178,1 | 4,2 |
| Số mã có trung vị dưới 1 tỷ đồng/phiên | 0/30 | 11/30 |
| Số mã có trung vị dưới 5 tỷ đồng/phiên | 0/30 | 16/30 |
| Tỷ lệ dòng thiếu dữ liệu khối ngoại | 1,6% | 43,1% |
| Số mã thiếu khối ngoại ở mọi phiên | 0 | 5 |

## Kết luận

- Với mã giao dịch vài trăm triệu đồng mỗi phiên, % thay đổi giá phản ánh vài lệnh lẻ nhiều hơn là động lượng; sổ lệnh ba mức rất mỏng nên chỉ báo cung–cầu không ổn định.
- Gần một nửa số dòng HNX30 không có dữ liệu khối ngoại, nên yếu tố dòng tiền ngoại không tính được cho nhiều mã. Ở chế độ cuối ngày chỉ 17/30 mã HNX30 đủ điều kiện xếp hạng.
- Vì vậy sản phẩm chỉ xếp hạng rổ VN30. Bộ giải mã vẫn đọc được mã sàn HNX nếu sau này mở rộng.

Chi tiết từng mã: [vn30_hnx30_thanh_khoan.csv](vn30_hnx30_thanh_khoan.csv).
