# Dữ liệu cho bản triển khai web

`ssi_daily.sqlite`: dữ liệu tổng hợp từng phiên của 30 mã VN30 (và dòng chỉ số VN30) lấy từ SSI FastConnect V3 (REST `securitiesSummary`). GitHub Actions cập nhật sau mỗi phiên (`.github/workflows/ssi-daily.yml`). Vercel đọc file này ở chế độ chỉ đọc. Không chứa khóa API.

`ssi_daily_foreign_supplements.json` ghi số liệu khối ngoại đối chiếu theo mã và ngày. Dashboard sử dụng bản ghi đối chiếu khi cả bốn trường mua và bán của SSI đều trống. Chi tiết mã và tệp CSV ghi tên nguồn bổ sung. Bản ghi GVR ngày 10/11/2026 dùng [bảng giao dịch của Stockbiz](https://web.stockbiz.vn/Stocks/GVR/ForeignerTrading.aspx), nơi công bố 0 cho cả khối lượng và giá trị mua và bán.
