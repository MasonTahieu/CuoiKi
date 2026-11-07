# Chuyển sang SSI FastConnect — 04/11/2026

> Phạm vi sau đó thu hẹp về **VN30** (07/11/2026). Nội dung dưới giữ nguyên để truy vết. [Lý do](../evidence/v3_history/PHAM_VI_VN30.md)

Người học xác nhận giảng viên đã chấp thuận thay NEO bằng SSI. Nguồn chính mới là SSI;
phạm vi VN30 và HNX30, xếp hạng trong phiên theo bốn yếu tố. Hiện người học **chưa đăng ký SSI**.
Không cần cung cấp bằng chứng chấp thuận bổ sung để tiếp tục phần đã được người học cho phép.

## 1. Đăng ký trước, chọn đúng phiên bản sau

SSI có tài liệu cho hai luồng; không dùng chéo bộ khóa, endpoint hoặc giao thức streaming.

| Luồng tài liệu | Khóa | Phần dự án đã chuẩn bị |
|---|---|---|
| FastConnect Data (FCData v2) | ConsumerID + ConsumerSecret | REST đọc thành phần chỉ số và DailyStockPrice, kiểm thử mock |
| FastConnect V3 | API Key + API Secret; một số chức năng SDK có cấu hình bổ sung | Nhận diện loại cấu hình; chưa triển khai collector V3 |

Cấu hình mặc định `SSI_API_PROFILE=unselected`, không tự đoán dịch vụ được cấp.
Nguồn: [FCData](https://guide.ssi.com.vn/ssi-products/fastconnect-data/connection-guide),
[V3](https://developers.ssi.com.vn/docs/getting-started/overview).

**Việc người học cần làm:**

1. Có tài khoản SSI; nếu chưa có thì mở tài khoản theo quy trình chính thức.
2. Đăng ký dịch vụ dữ liệu FastConnect với SSI. Nêu rõ nhu cầu REST và realtime cho HOSE/HNX,
   giá/giao dịch, sổ lệnh và khối ngoại; hỏi phiên bản được cấp, hạn mức và điều kiện sử dụng dữ liệu cho đồ án.
3. Theo hướng dẫn kích hoạt SSI gửi. Chỉ gửi cho trợ lý tên phiên bản/đường link hướng dẫn và loại bộ khóa.
4. Khi có khóa, lưu tại `.env` của dự án; không đưa khóa vào chat.

Hướng dẫn [FCData/iBoard](https://www.ssi.com.vn/khach-hang-ca-nhan/giao-dich-chung-khoan-ib-web)
nêu đăng ký qua SSI rồi tạo key tại iBoard. Hướng dẫn [V3](https://developers.ssi.com.vn/docs/getting-started/registration)
nêu liên hệ chi nhánh/PGD hoặc 1900545471; [tạo key V3](https://developers.ssi.com.vn/docs/getting-started/api-keys)
qua Developer Portal. Ưu tiên quy trình và tài liệu gắn với dịch vụ SSI thực tế cấp cho tài khoản.
Chưa khẳng định tài khoản đã có quyền hoặc dữ liệu realtime chỉ vì xem được trang tài liệu.

## 2. Khả năng dữ liệu đối với đề tài

| Nhu cầu | FCData dự kiến | Điều phải xác minh |
|---|---|---|
| Thành phần VN30/HNX30 | IndexList + IndexComponents | Index code thực, phân trang, ngày hiệu lực và đủ thành phần |
| Động lượng trong phiên | Snapshot X/Trade, B OHLCV | Giá khớp gần nhất, mở cửa, phiên và thời gian nguồn |
| Thanh khoản | Tổng khớp; Quote bid/ask | Phạm vi tổng, đơn vị; không dùng Volume phát sinh thay cộng dồn |
| Khối ngoại | R, DailyStockPrice | Giá trị/khối lượng và độ mới; REST ngày không mặc định là intraday |
| Cung–cầu | X-Quote | Lấy cùng ba mức cho HOSE/HNX; không so 3 mức HOSE với 10 mức HNX |
| Trạng thái | F | Phiên LO và trạng thái N cần ánh xạ; không mặc định tất cả NORMAL |
| Lịch sử | DailyOhlc, IntradayOhlc | Quyền, độ dài, điều chỉnh và độ đầy đủ; chưa mở rộng phương pháp nhiều ngày |

[REST](https://guide.ssi.com.vn/ssi-products/fastconnect-data/api-specs)
[Streaming](https://guide.ssi.com.vn/ssi-products/fastconnect-data/streaming-data)

**Khối ngoại cần chú ý:** tài liệu R ghi giá trị ngoại HOSE có thể tính gần đúng bằng khối lượng nhân giá gần nhất.
Vì vậy không trình bày là dòng tiền giá trị chính xác. Tài liệu bảng dùng FBuyVal/FSellVal nhưng ví dụ dùng BuyVal/SellVal;
DailyStockPrice cũng có cách viết trường khác nhau. Chốt adapter bằng mẫu thực, ghi cờ ước tính,
và kiểm tra độ nhạy với tỷ lệ khối lượng trước khi nghiệm thu phương pháp.
Giá trị ngoại ước tính có thể giảm khi giá thị trường giảm; không bê nguyên giả định cộng dồn đơn điệu từ NEO sang trường này.

## 3. Những phần đã chuyển

- Mặc định DATA_PROVIDER=ssi; chỉ nạp cấu hình của nguồn được chọn, không lấy token NEO để xác thực SSI.
- Store chấp nhận nguồn ssi, kho mặc định runtime/ssi.sqlite tách khỏi NEO; lọc khóa nhạy cảm.
- Canonical schema là hợp đồng nội bộ, tên trường cũ không đồng nghĩa dữ liệu đang lấy từ NEO.
- Giữ thông tin index_group và marketCode; xếp hạng riêng từng nhóm, tối thiểu 10 mã hợp lệ mỗi nhóm.
- Demo hai nhóm dùng 24 mã hư cấu, 75 sự kiện, không phải thành phần thật của hai chỉ số.
- UI chọn nhóm trước bộ lọc hiển thị; điểm được tính riêng trong nhóm và không đổi khi lọc mã.
- Điểm dữ liệu SSI bị khóa đến khi SSI_SEMANTICS_VERIFIED=true sau xác minh thực tế.
- FCData v2 REST client có allowlist market-only, khoảng nghỉ 1 giây trong một tiến trình
  (giới hạn phòng vệ của ứng dụng, không khẳng định là quota của SSI), không theo redirect hoặc retry login.

## 4. Chạy hiện tại và kiểm tra khi có khóa

```powershell
.\RUN_APP.ps1
& "$HOME\.venv\Scripts\Activate.ps1"
python -X utf8 -m src.cli readiness
python -X utf8 -m src.cli demo-pipeline
```

Nếu dùng cấu hình cũ có DATA_PROVIDER=neo thì đổi rõ thành ssi; chương trình không tự sửa bí mật trong .env.
`readiness` không gọi mạng và không in giá trị khóa.

**Chỉ khi được cấp FCData v2:** điền SSI_API_PROFILE=fcdata_v2, SSI_CONSUMER_ID và SSI_CONSUMER_SECRET vào .env, rồi chạy:

```powershell
python -X utf8 -m src.cli collect --transport rest
```

Lệnh xác thực rồi lấy hai nhóm và dữ liệu DailyStockPrice đúng ngày hiện tại, lưu bản thô và bảng ánh xạ.
**REST probe này chưa đủ để xếp hạng intraday:** không tự tạo bid/ask, phiên LO hoặc trạng thái NORMAL.
Ngày nghỉ/ngoài giờ có thể chưa có dữ liệu đúng ngày. Không lấy ngày cũ rồi gắn nhãn ngày mới.
Nếu được cấp V3, cần hoàn thiện adapter V3 từ tài liệu được cấp; client v2 chủ động từ chối.

## 5. Phần còn phải làm

- Xác nhận phiên bản, khóa, quyền và schema thực tế; xử lý sai khác endpoint giữa các phiên bản tài liệu.
- Xây collector streaming SSI bằng client chính thức tương ứng; hiện lệnh collect --transport ws của SSI dừng rõ ràng.
- Ánh xạ X/Quote/Trade/R/F vào canonical, giữ thời gian từng trường, snapshot/patch và cờ ước tính.
- Kiểm tra bootstrap, mất kết nối, phiên từng sàn, đơn vị và mẫu số ngoại cùng phạm vi.
- Lưu nhiều phiên và đánh giá độ phủ, độ trễ, hiệu năng, độ nhạy thứ hạng.
- Cập nhật bài báo cáo theo nguồn SSI được giảng viên chấp thuận; gói nộp theo quy cách giảng viên xác nhận.

Không dùng kết quả giả lập làm bằng chứng chất lượng SSI hay hiệu quả đầu tư.
Tên thư mục neo-vn30-screener được giữ để không làm hỏng đường dẫn cũ; đó không phải nguồn đang được chọn.
