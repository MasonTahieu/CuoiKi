# Task 4 — Đối chiếu bốn yếu tố

Dữ liệu giả lập gồm 11 mã VN30 hư cấu. Các thứ tự yếu tố được thiết kế để kiểm tra sự đánh đổi khi chấm điểm.

## Ca tính tay

Giá cuối 110, mở cửa 100, tổng giá trị khớp 10.000. Giá mua 99/98/97, giá bán 101/102/103.
Ba mức mua có 200 đơn vị mỗi mức, ba mức bán có 100 mỗi mức.
Ngoại mua/bán theo giá trị là 1.000/3.000 và theo khối lượng là 120/40 trên tổng 400.

| Ca | Động lượng | Spread (bps) | Độ sâu | Tỷ lệ ngoại | Cung–cầu |
|---|---:|---:|---:|---:|---:|
| Giá trị, spread 2 | 10.00% | 200.00 | 89,400 | -20.00% | 0.3333 |
| Giá trị, spread 1 | 10.00% | 100.00 | 89,450 | -20.00% | 0.3333 |
| Giá trị, độ sâu giảm 90% | 10.00% | 200.00 | 8,940 | -20.00% | 0.3333 |
| Khối lượng, cùng snapshot | 10.00% | 200.00 | 89,400 | 20.00% | 0.3333 |

## So sánh thứ hạng

Thứ tự trọng số là động lượng, thanh khoản, khối ngoại, cung–cầu. Mốc so sánh dùng giá trị và 25/25/25/25.
Các mã đồng hạng 3 đều được tính vào nhóm dẫn đầu.

| Nhóm | Cấu hình so với mốc | Mã đổi hạng | Dịch hạng lớn nhất | Mã giữ vị trí trong nhóm dẫn đầu |
|---|---|---:|---:|---:|
| VN30 | Giá trị, 40/20/20/20 | 10/11 | 4 | 2/3 |
| VN30 | Khối lượng, 25/25/25/25 | 11/11 | 8 | 1/3 |

Khi giảm nhóm còn 9 mã (dưới ngưỡng tối thiểu 10), số mã được xếp hạng là **0**: hệ thống không xếp hạng một nhóm quá nhỏ.

## Đóng góp vào tổng điểm của HOSETEST11

| Cấu hình | Động lượng | Thanh khoản | Khối ngoại | Cung–cầu | Tổng | Hạng |
|---|---:|---:|---:|---:|---:|---:|
| Giá trị, 25/25/25/25 | 25.00 | 0.00 | 25.00 | 5.00 | 55.00 | 4 |
| Giá trị, 40/20/20/20 | 40.00 | 0.00 | 20.00 | 4.00 | 64.00 | 1 |
| Khối lượng, 25/25/25/25 | 25.00 | 0.00 | 17.50 | 5.00 | 47.50 | 7 |

Tổng điểm là tổng bốn đóng góp. Mỗi đóng góp bằng điểm phân vị nhân trọng số.
Mỗi so sánh dùng cùng tập mã tại cùng một mốc. Cấu hình theo khối lượng dùng cho kiểm chứng offline.

Đầu vào, thứ hạng và đóng góp từng mã có trong bảng chi tiết. [Mở JSON](doi_chieu.json)
Tái tạo bằng `python -X utf8 -m src.ranking.verify_factors`.

Xem [đặc tả và điều kiện kiểm chứng SSI](../../docs/TASK_4_KIEM_CHUNG_BON_YEU_TO.md).
