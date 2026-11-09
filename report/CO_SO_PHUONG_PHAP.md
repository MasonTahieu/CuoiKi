# Cơ sở tài chính của phương pháp (bản nháp cho mục 5 báo cáo)

Bản nháp này nêu từng yếu tố dựa trên tài liệu nào và **khác tài liệu đó ở đâu**. Thông tin xuất bản và kết luận chính đã đối chiếu qua tóm tắt và trang thư mục của các bài. Toàn văn chưa được đọc, nên người viết báo cáo cần đọc bài gốc trước khi trích chi tiết hơn những gì ghi ở đây.

## Sản phẩm khẳng định gì và không khẳng định gì

Sản phẩm **mô tả** vị trí tương đối của các mã VN30 tại một mốc, để thu hẹp danh sách cần nghiên cứu tiếp. Sản phẩm **không khẳng định** điểm cao thì giá sẽ tăng. Các tài liệu dưới đây là lý do chọn những biến này để theo dõi, không phải bằng chứng rằng điểm tổng hợp dự báo được lợi suất. [Kiểm tra phiên kế tiếp](../evidence/v3_sessions/KIEM_TRA_PHIEN_KE_TIEP.md) trên dữ liệu thật hiện chưa cho thấy liên hệ như vậy.

## Từng yếu tố

| Yếu tố | Công thức trong sản phẩm | Cơ sở | Khác biệt cần nêu |
|---|---|---|---|
| Động lượng | % giá khớp so với giá mở cửa | Jegadeesh (1990): lợi suất tháng có tự tương quan âm ở độ trễ một tháng, dương ở độ trễ dài hơn | Bài dùng dữ liệu tháng, sản phẩm đo trong một phiên. Không dùng bài này để nói động lượng trong phiên dự báo được giá |
| Thanh khoản | Trung bình phân vị của giá trị khớp, độ sâu ba mức và chênh lệch mua–bán (dữ liệu ngày: chỉ giá trị khớp) | Amihud (2002): tính kém thanh khoản kỳ vọng làm tăng lợi suất kỳ vọng; thước đo là \|lợi suất\| / giá trị giao dịch | Sản phẩm không dùng thước đo Amihud. Giá trị khớp tuyệt đối nghiêng về mã vốn hóa lớn (xem Hạn chế) |
| Dòng tiền ngoại | (mua − bán của khối ngoại) / giá trị khớp | Froot, O'Connell & Seasholes (2001): dòng vốn bền, chịu ảnh hưởng của lợi suất quá khứ; ở thị trường mới nổi, dòng vào có khả năng dự báo lợi suất. Vo (2017): khối ngoại ở Việt Nam giao dịch theo xu hướng | Froot và cộng sự đo dòng vốn xuyên biên giới cấp thị trường; sản phẩm đo tỷ lệ theo từng mã trong một phiên |
| Cung–cầu | (khối lượng chào mua − chào bán) / tổng khối lượng chào ở ba mức giá | Chordia, Roll & Subrahmanyam (2002): mất cân bằng lệnh theo ngày liên hệ với thanh khoản và lợi suất toàn thị trường. Cont, Kukanov & Stoikov (2014): trong khoảng ngắn, biến động giá chủ yếu do mất cân bằng dòng lệnh tại giá tốt nhất | Hai bài đo **dòng lệnh**. Sản phẩm đo **khối lượng đang chờ** tại một mốc, nên chỉ là thước đo gần đúng |

## Cách kết hợp

- **Xếp hạng phân vị trong nhóm:** các yếu tố có đơn vị khác nhau được đưa về cùng thang 0–100. Một giá trị cực đoan không kéo lệch cả thang như khi dùng trung bình và độ lệch chuẩn.
- **Trọng số:** 25/25/25/25 và 40/20/20/20 (dữ liệu ngày: 33/33/33 và 50/25/25) là lựa chọn thiết kế, không ước lượng từ dữ liệu. Trên 15 phiên thật, đổi cấu hình gần như không đổi kết quả (Spearman 0,96).
- **Không tự chia lại trọng số:** mã thiếu một yếu tố thì không được xếp hạng, kèm lý do.

## Kiểm định

- **Vì sao không coi |t| vừa trên 2 là phát hiện:** Harvey, Liu & Zhu (2016) cho rằng ngưỡng t khoảng 2 là quá thấp khi nhiều yếu tố đã được thử, và đề xuất ngưỡng trên 3 cho yếu tố mới. Dự án có nhiều phép đo trên 15 phiên, nên áp dụng cùng tinh thần thận trọng.
- **Vì sao tính lợi suất từ giá mở cửa phiên sau:** điểm chỉ có sau khi đóng cửa, nên phần chênh lệch qua đêm không thể giao dịch theo điểm.

## Hạn chế cần nêu

- Mô hình bốn yếu tố trong phiên chưa có kết quả trên dữ liệu thật tại thời điểm viết bản nháp này.
- Điểm thanh khoản gần như không đổi giữa các phiên (Spearman 0,87), trong khi động lượng gần như không lặp lại (0,00). Khoảng một phần ba điểm vì thế phản ánh quy mô giao dịch hơn là diễn biến của phiên.
- Trung bình 10,4/30 mã có điểm trùng với mã khác mỗi phiên, do phân vị rời rạc và trọng số bằng nhau.
- Chênh lệch giá theo bps chịu ảnh hưởng của bước giá theo vùng giá của HOSE, nên không hoàn toàn so sánh được giữa các vùng giá.
- Số khối ngoại của SSI gồm cả giao dịch thỏa thuận, còn giá trị khớp thì không, nên yếu tố khối ngoại không đo riêng áp lực khớp lệnh. Dữ liệu ngày không tách được phần này. Trong trường hợp xấu nhất trên 6 phiên, tổng điểm có Spearman trung bình 0,95 so với bản gốc và giữ 3,8/5 mã top 5. [Kết quả](../evidence/v3_history/KHOI_NGOAI_THOA_THUAN.md)
- Danh sách VN30 lấy theo thời điểm thu thập, không theo từng ngày trong quá khứ.

## Tài liệu tham khảo

- Amihud, Y. (2002). Illiquidity and stock returns: cross-section and time-series effects. *Journal of Financial Markets*, 5(1), 31–56.
- Chordia, T., Roll, R., & Subrahmanyam, A. (2002). Order imbalance, liquidity, and market returns. *Journal of Financial Economics*, 64(1), 111–130.
- Cont, R., Kukanov, A., & Stoikov, S. (2014). The price impact of order book events. *Journal of Financial Econometrics*, 12(1), 47–88.
- Froot, K. A., O'Connell, P. G. J., & Seasholes, M. S. (2001). The portfolio flows of international investors. *Journal of Financial Economics*, 59(2), 151–193.
- Harvey, C. R., Liu, Y., & Zhu, H. (2016). … and the cross-section of expected returns. *Review of Financial Studies*, 29(1), 5–68.
- Jegadeesh, N. (1990). Evidence of predictable behavior of security returns. *Journal of Finance*, 45(3), 881–898.
- Vo, X. V. (2017). Trading of foreign investors and stock returns in an emerging market: Evidence from Vietnam. *International Review of Financial Analysis*, 52, 88–93.
