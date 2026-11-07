# Task 4 — Kiểm chứng bốn yếu tố

Hoàn thành kiểm chứng offline ngày **05/11/2026**. Bảng mẫu dùng 11 mã giả lập mỗi nhóm, với thứ tự các yếu tố được thiết kế để thấy rõ sự đánh đổi khi xếp hạng. [Kết quả mẫu](../evidence/task4/KET_QUA_MAU.md)

## Công thức

| Yếu tố | Số liệu thô và cách chấm |
|---|---|
| Động lượng | 100 × (giá khớp gần nhất / giá mở cửa − 1). Giá trị cao hơn nhận phân vị cao hơn. |
| Thanh khoản | Trung bình ba điểm phân vị của giá trị khớp, độ sâu giá trị ba mức và spread. Spread hẹp hơn nhận điểm cao hơn. Độ sâu là tổng giá × khối lượng của sáu mức. Spread (bps) là 10.000 × (giá bán 1 − giá mua 1) / giá giữa. |
| Khối ngoại theo giá trị | (Giá trị ngoại mua − giá trị ngoại bán) / tổng giá trị khớp cùng phạm vi. Đây là cấu hình mặc định `intraday-v1`. |
| Khối ngoại theo khối lượng | (Khối lượng ngoại mua − khối lượng ngoại bán) / tổng khối lượng khớp cùng phạm vi. Đây là cấu hình đối chiếu `intraday-foreign-volume-v1`. |
| Cung–cầu | (Khối lượng chào mua − khối lượng chào bán) / tổng khối lượng chào hai bên, tính trên ba mức mỗi bên. |

Ca tính tay với giá mở cửa 100, giá cuối 110 cho động lượng 10%. Spread 2 trên giá giữa 100 cho 200 bps.
Độ sâu là (99 + 98 + 97) × 200 + (101 + 102 + 103) × 100 = 89.400. Cung–cầu là (600 − 300)/900 = 1/3.
Ngoại theo giá trị cho (1.000 − 3.000)/10.000 = −20%. Ngoại theo khối lượng cho (120 − 40)/400 = +20%.
Ca thu hẹp spread còn 100 bps và ca giảm độ sâu còn 8.940 cũng được kiểm độc lập. Kiểm thử thanh khoản giữ giá trị khớp cố định ở ba ca để đối chiếu điểm phân vị.

## Cấu hình và điều kiện xếp hạng

- `rank_groups(frame, foreign_basis="volume")` chọn công thức khối lượng cho cả snapshot. Mỗi mã dùng cùng một công thức trong cấu hình đó.
- Cấu hình khối lượng dùng `foreignBuyVolume`, `foreignSellVolume` và `totalTradingVolume`. Trường phải hữu hạn và không âm, mẫu số phải dương, tỷ lệ phải thuộc [−1, 1]. Thiếu hoặc sai trường thì mã bị loại kèm lý do. `foreign_net_volume` lưu khối lượng ròng.
- Điểm từng yếu tố là phân vị trong nhóm hợp lệ tại cùng thời điểm. Giá trị bằng nhau nhận hạng phân vị trung bình. Cả nhóm bằng nhau nhận 50 điểm ở yếu tố đó.
- Mỗi nhóm cần ít nhất 10 mã hợp lệ. Tổng điểm là tổng bốn điểm phân vị nhân trọng số, làm tròn 10 chữ số trước khi xếp hạng. Các mã đồng điểm dùng hạng nhỏ nhất.
- `method_version` phân biệt hai công thức. `config_id` ghi nhận phương pháp, trọng số, nhóm và ngưỡng số mã. `cohort_id` theo tập mã thực sự được dùng để tính phân vị.

Mẫu đối chiếu giữ cố định 11 mã hợp lệ ở mỗi nhóm và so ba cấu hình. Mốc là giá trị với trọng số đều 25/25/25/25. Một ca tăng động lượng lên 40/20/20/20 và giữ công thức ngoại. Ca còn lại đổi công thức ngoại sang khối lượng và giữ trọng số đều.
Nếu hai công thức cho tập mã hợp lệ khác nhau trên dữ liệu thật, cần đối chiếu thêm trên phần giao để tách ảnh hưởng công thức khỏi ảnh hưởng thay đổi nhóm so sánh.

## Kiểm tra giá trị ngoại ước tính

Ca replay SSI giả lập hạ giá khớp từ 20.000 xuống 15.000. Ngoại mua tăng từ 2.000 lên 2.001 cổ phiếu trong khi giá trị ước tính giảm từ 40.000.000 xuống 30.015.000. Replay giữ cờ ước tính và mã vẫn qua kiểm tra dữ liệu ở mốc đó. Khi tổng khối lượng khớp hoặc khối lượng ngoại sau đó giảm, replay ghi nhận lỗi counter.

Cấu hình khối lượng đang dùng để kiểm chứng offline với các trường cùng phạm vi và cùng mốc. Để chốt công thức SSI, cần đối chiếu phạm vi khớp lệnh, đơn vị và thời điểm cập nhật hai tử số/mẫu số trên dữ liệu thật. Cổng xác minh SSI vẫn áp dụng cho cả hai cấu hình. Mức đổi hạng trong mẫu đo độ nhạy của công thức trên các tình huống tự dựng. [Tài liệu trường dữ liệu SSI đã đối chiếu](FASTCONNECT_KET_NOI_VA_TASK_LAM_TRUOC.md)

## Tái tạo và kiểm thử

Chạy từ thư mục dự án.

```powershell
& "$HOME\.venv\Scripts\Activate.ps1"
python -X utf8 -m src.ranking.verify_factors
python -m pytest -q tests/test_factor_verification.py
```

10 kiểm thử mới của task 4 đạt, ca hồi quy replay giá giảm đạt, toàn dự án đạt **191 kiểm thử**. [Kết quả pytest](../evidence/task4-tests.xml)
