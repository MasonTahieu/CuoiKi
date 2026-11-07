# Kết quả REST thật đầu tiên với SSI FastConnect API V3

> Phạm vi sau đó thu hẹp về **VN30** (07/11/2026). Nội dung dưới giữ nguyên để truy vết. [Lý do](PHAM_VI_VN30.md)

**Ngày chạy: 07/11/2026** (thứ Bảy, sàn nghỉ). Đây là **dữ liệu SSI thật**, lấy qua REST bằng API Key của người học. Đăng nhập không cần OTP. Chưa có dữ liệu stream trong phiên.

Lệnh đã chạy:

```powershell
.\SSI_V3.ps1 -Lenh lichsu -SoPhien 10
.\SSI_V3.ps1 -Lenh danhgia
```

- Kho dữ liệu: `runtime/ssi_daily.sqlite`, không đưa vào gói nộp.
- Kết quả đánh giá: `evidence/v3_sessions/evaluation.json`.

## 1. Hành vi thật của các endpoint (khác tài liệu SDK ở một điểm)

| Endpoint | Kết quả quan sát | So với giả định trong code |
|---|---|---|
| `data/securitiesByBoard?index=VN30` | Danh sách 30 mã, `board` = HOSE | Đúng. Phần khởi tạo danh sách mã của stream dùng được |
| `data/securitiesByBoard?index=HNX30` | Danh sách 30 mã, `board` = HNX | Đúng |
| `data/securitiesSummary?index=VN30` | **Trả về chính chỉ số VN30** (điểm khoảng 1.846), mỗi ngày 1 dòng | **Khác** tài liệu SDK ("all members of an index"). Code đã sửa để lấy theo từng mã |
| `data/securitiesSummary?symbol=GVR` | Mỗi phiên 1 dòng; mọi số là chuỗi (`"29800"`); ngày dạng `2026/11/06`; có `pagesCount` | Đúng sau khi sửa. Bộ đọc đã xử lý chuỗi số và định dạng ngày này |
| `data/indexList` | 35 chỉ số | Không dùng cho xếp hạng |

Đơn vị: giá tính bằng **đồng** (trung vị giá đóng cửa 23.500 đ). Giá trị khớp và giá trị khối ngoại cũng tính bằng đồng.

## 2. Độ đầy đủ

| Chỉ tiêu | Kết quả |
|---|---|
| Phiên lấy được | 10 phiên: 26/10, 27/10, 28/10, 29/10, 30/10, 02/11, 03/11, 04/11, 05/11, 06/11 |
| Dòng theo mã | 599 / 600. Thiếu **SLS** (HNX30) ngày 03/11 |
| Giá mở cửa, đóng cửa, giá trị khớp | Không thiếu dòng nào |
| Giá trị mua/bán của khối ngoại | Để trống (null) ở **43,5% dòng HNX30** và 1,7% dòng VN30. CAP, DP3, PLC, NBC, L18, PVC, TVD, PSD để trống cả 10 phiên |

**Cần xác minh:** null ở trường khối ngoại có thể có nghĩa là "không có giao dịch khối ngoại" (ví dụ GVR có phiên trả `"0"`, có phiên trả null). Code **chưa** tự đổi null thành 0. Cần đối chiếu với gói `room` của stream trong phiên trước khi quyết định.

## 3. Kiểm chứng giả định "giá trị khớp = giá bình quân × khối lượng"

Gói `trade` của stream V3 không có tổng giá trị khớp, nên code suy ra bằng `a × v`. Trên 599 dòng ngày thật:

- Trung vị của tỷ lệ `average × totalMatch / totalMatchValue` = **1,0000**.
- Khoảng 5%–95% của tỷ lệ là 0,99998–1,00001.
- 98,7% số dòng nằm trong khoảng 0,98–1,02.

Kết quả này ủng hộ cách suy ra giá trị khớp trong phiên. Khi có stream, vẫn cần đối chiếu cuối phiên giữa stream và REST.

## 4. Đánh giá nhiều phiên (yếu tố theo ngày, không có sổ lệnh)

Mức giữ thứ hạng giữa hai ngày liên tiếp, đo bằng hệ số tương quan thứ hạng Spearman trung bình trên 9 cặp ngày:

| Yếu tố theo ngày | VN30 | HNX30 | Đọc kết quả |
|---|---|---|---|
| Thanh khoản (giá trị khớp) | 0,885 | 0,932 | Gần như luôn cùng các mã đứng đầu. Yếu tố này nghiêng về mã vốn hóa lớn, như đã nêu trong phần giới hạn |
| Dòng tiền ngoại tương đối | 0,432 | 0,330 | Ổn định ở mức vừa. HNX30 thiếu nhiều dữ liệu khối ngoại |
| Động lượng (đóng cửa so với mở cửa) | 0,055 | 0,048 | Thay đổi gần như hoàn toàn mỗi ngày, đúng bản chất yếu tố trong phiên |

Tương quan thứ hạng giữa các yếu tố, gộp các ngày:

| Cặp | VN30 | HNX30 |
|---|---|---|
| động lượng ~ thanh khoản | 0,054 | −0,076 |
| động lượng ~ khối ngoại | 0,343 | 0,126 |
| thanh khoản ~ khối ngoại | 0,182 | 0,169 |

Các yếu tố có tương quan thấp, nên mỗi yếu tố đóng góp thông tin riêng vào điểm tổng. Đây là căn cứ cho cách chấm đa yếu tố.

**Giới hạn của phần này:**
- Dữ liệu ngày không có sổ lệnh, nên chưa có yếu tố cung–cầu và chưa có điểm bốn yếu tố trong phiên.
- Các con số trên mô tả độ ổn định của thứ hạng, **không** đo khả năng dự báo lợi suất.

## 5. Việc tiếp theo

1. Thứ Hai 09/11, trong giờ khớp lệnh liên tục: `.\SSI_V3.ps1 -Lenh smoke -Giay 60` để kiểm tra stream, định dạng thời gian `t`, cờ phiên, số mức sổ lệnh và quyền đăng ký topic theo rổ.
2. Đối chiếu null của khối ngoại với gói `room` trong phiên.
3. Thu ít nhất 5 phiên bằng `.\SSI_V3.ps1 -Lenh phien`, rồi đánh giá xếp hạng trong phiên.
