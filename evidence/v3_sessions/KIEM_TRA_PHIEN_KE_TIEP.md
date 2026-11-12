# Kiểm tra phiên kế tiếp: điểm cuối ngày và lợi suất phiên sau

Dữ liệu SSI thật, rổ VN30, **19 phiên**, 18 cặp phiên liên tiếp. Không có tham số nào được ước lượng. Trọng số chọn trước khi tính phép đo này. Điểm phiên t chỉ dùng dữ liệu phiên t.

## Lợi suất mua được

Tính từ mở cửa → đóng cửa của phiên t+1 (mua được sau khi có điểm).

| Cấu hình | IC trung bình | Độ lệch chuẩn | t | Tỷ lệ cặp IC > 0 | Top 5 − Bottom 5 (điểm %) | t |
|---|---:|---:|---:|---:|---:|---:|
| Cân bằng 33/33/33 | +0,015 | 0,241 | +0,27 | 50% | −0,07 | −0,31 |
| Ưu tiên động lượng 50/25/25 | +0,022 | 0,234 | +0,39 | 50% | +0,06 | +0,24 |

## So sánh: tính cả chênh lệch qua đêm

Tính theo priceChangePercent của phiên t+1 do SSI tính (gồm cả chênh lệch qua đêm, không mua kịp).

| Cấu hình | IC trung bình | Độ lệch chuẩn | t | Tỷ lệ cặp IC > 0 | Top 5 − Bottom 5 (điểm %) | t |
|---|---:|---:|---:|---:|---:|---:|
| Cân bằng 33/33/33 | −0,054 | 0,230 | −1,00 | 50% | −0,17 | −0,71 |
| Ưu tiên động lượng 50/25/25 | −0,049 | 0,212 | −0,99 | 39% | −0,13 | −0,57 |

## IC của từng yếu tố (cấu hình cân bằng, lợi suất mua được)

| Yếu tố | IC trung bình | t |
|---|---:|---:|
| Động lượng | +0,008 | +0,16 |
| Thanh khoản | +0,028 | +0,66 |
| Dòng tiền ngoại | −0,012 | −0,30 |

## Kết luận

Chưa có bằng chứng điểm liên hệ với lợi suất phiên sau (IC trung bình +0,015, t = +0,27, 18 cặp phiên). Với cỡ mẫu này chỉ phân biệt được IC từ khoảng 0,11 trở lên. Điểm dùng để thu hẹp danh sách, không phải tín hiệu mua bán.

- **Độ nhạy:** mẫu này chỉ phân biệt được IC trung bình từ khoảng 0,11 trở lên. Muốn phát hiện IC 0,05 cần khoảng 95 phiên. Vì vậy kết quả là "chưa có bằng chứng", không phải "đã chứng minh không dự báo được".
- **Kiểm định nhiều lần:** có nhiều phép đo trên cùng mẫu, nên một giá trị |t| vừa trên 2 chưa đủ để coi là phát hiện.
- **Điều chỉnh quyền:** `refPrice` trống ở mọi dòng. Có 2/540 dòng `priceChangePercent` lệch quá 0,3 điểm % so với đóng cửa/đóng cửa (GVR 2026-10-21, VNM 2026-10-22). Cần đối chiếu với lịch giao dịch không hưởng quyền.
- Kết quả không thay đổi cách chấm điểm. Sản phẩm không trình bày điểm như xác suất tăng giá.

Chi tiết từng cặp phiên: [kiem_tra_phien_ke_tiep.csv](kiem_tra_phien_ke_tiep.csv). Tạo lại: `python -X utf8 -m src.cli evaluate-v3`.
