# Số khối ngoại của SSI có gồm giao dịch thỏa thuận không

**Kết luận:** có. Giá trị mua và bán của khối ngoại trong cả stream và REST gồm giao dịch thỏa thuận khi khối ngoại tham gia. Giá trị khớp (`totalTradingValue`) không gồm thỏa thuận, nên tỷ lệ khối ngoại có tử số rộng hơn mẫu số.

Dữ liệu: bản thu stream 09/11/2026 13:34–15:05 và 16 phiên REST 19/10–09/11/2026, rổ VN30. Bằng chứng trực tiếp chỉ có từ một buổi chiều. Các phiên trước chỉ có bằng chứng gián tiếp ở mục 2.

## 1. Bằng chứng trực tiếp từ stream 09/11

Sau 14:45 không còn khớp lệnh, nhưng gói ROOM lúc 14:49 vẫn tăng. Số đo là mức tăng so với gói ROOM lúc 14:48.

| Mã | Mua tăng (đồng) | Bán tăng (đồng) | Khớp lệnh quanh phút đó | Thỏa thuận theo REST (đồng) |
|---|---|---|---|---|
| FPT | 19.598.646.800 | 19.598.646.800 | 0 | 19.598.646.800 |
| VNM | 9.306.656.800 | 9.306.656.800 | 0 | 9.306.656.800 |

Hai mã trên khớp đến từng đồng. Mua và bán tăng bằng nhau cho thấy cả hai bên của giao dịch đều là khối ngoại.

Trước 14:45 cũng có các bước nhảy vượt xa khớp lệnh. Khung so sánh mở rộng thêm 90 giây mỗi phía:

| Mã, thời điểm | Bên tăng | Khối ngoại tăng (tỷ) | Khớp lệnh trong khung (tỷ) | Thỏa thuận cả ngày theo REST (tỷ) |
|---|---|---|---|---|
| VPB, 13:55 | Chỉ mua | 75,163 | 7,729 | 74,160 |
| MWG, 14:05 | Mua và bán | 30,994 | 2,350 | 29,957 |
| TCB, 14:49 | Mua và bán | 2,625 | 0 | 9,809 |

Trong toàn bộ 1.907 lần khối ngoại tăng, 9 lần vượt khung khớp lệnh, thuộc 5 mã trên. Lần chạy không ghi được trước 13:34.

Các mã có thỏa thuận lớn nhưng không có bước nhảy khối ngoại trong bản thu là LPB (727 tỷ), SHB (352 tỷ), VJC (314 tỷ). Có thể các giao dịch này không có khối ngoại, hoặc diễn ra trước 13:34; bản thu không phân biệt được.

## 2. Bằng chứng gián tiếp từ 16 phiên REST

- **Khối ngoại lớn hơn tổng khớp:** 3 dòng (ACB 20/10, ACB 27/10, VNM 29/10). Khớp lệnh đơn thuần không tạo ra được điều này.
- **Giá bình quân khối ngoại nằm ngoài biên độ thấp–cao của phiên:** 20 dòng (MWG 11, TCB 8, VPB 1). Ví dụ MWG 23/10 có giá bình quân 80.500 trong khi biên độ là 74.600–75.500.
- **MWG mua gần bằng bán:** trung vị chênh lệch 1,7% giữa hai bên, phù hợp với khối ngoại giao dịch với nhau. Đây là suy luận từ số liệu, chưa có nguồn xác nhận.

## 3. Trường thỏa thuận của REST không đủ để loại trừ

`ptTotalTradedValue` trống ở 210/480 dòng, bằng 0 ở 161 dòng và dương ở 109 dòng. Mọi giá trị dương đều từ 02/11 trở đi, dù các phiên tháng 10 vẫn có dấu hiệu ở mục 2. Trường này cũng là tổng của cả mã, không cho biết phần nào do khối ngoại. Vì vậy không thể tách chính xác phần thỏa thuận khỏi số khối ngoại trên dữ liệu ngày.

## 4. Mức ảnh hưởng tới xếp hạng

Giao dịch khối ngoại với khối ngoại không đổi giá trị ròng, nên không đổi tử số của tỷ lệ. Giao dịch một phía thì có đổi: VPB ngày 09/11 có ròng +84,9 tỷ, trong đó thỏa thuận cả ngày là 74,2 tỷ.

Phép thử trường hợp xấu nhất giả định toàn bộ thỏa thuận của mã là một phía khối ngoại và cùng chiều với giá trị ròng, rồi trừ khỏi ròng. Chỉ 6 phiên từ 02/11 có số thỏa thuận để thử, cấu hình cân bằng:

| Phiên | Spearman tổng điểm | Spearman điểm khối ngoại | Số mã giữ trong top 5 |
|---|---|---|---|
| 02/11 | 0,955 | 0,894 | 5 |
| 03/11 | 0,962 | 0,877 | 4 |
| 04/11 | 0,979 | 0,901 | 4 |
| 05/11 | 0,940 | 0,840 | 3 |
| 06/11 | 0,963 | 0,913 | 3 |
| 09/11 | 0,895 | 0,851 | 4 |
| Trung bình | 0,949 | 0,876 | 3,8 |

Kiểm tra phiên kế tiếp trên 15 cặp phiên: IC +0,022 (t = +0,37) với số gốc và +0,029 (t = +0,48) với số đã trừ. Cả hai đều không có bằng chứng dự báo, nên kết luận không đổi. Phép thử này chỉ cho biết độ nhạy, không phải số đã làm sạch; 10 phiên tháng 10 không kiểm tra được.

## 5. Cách diễn giải trong dự án

- Yếu tố khối ngoại đo dòng tiền ròng của khối ngoại **gồm cả thỏa thuận**, không phải riêng áp lực khớp lệnh.
- Một lô thỏa thuận một phía có thể đưa một mã lên cao ở yếu tố này, và có thể đổi 1–2 mã trong top 5 theo phép thử trên.
- Stream có thể phát hiện bước nhảy như mục 1, nhưng dữ liệu ngày thì không. Dự án chưa loại phần này khỏi điểm.
