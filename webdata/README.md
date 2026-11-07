# Dữ liệu cho bản triển khai web

`ssi_daily.sqlite`: dữ liệu tổng hợp từng phiên của 30 mã VN30 (và dòng chỉ số VN30) lấy từ SSI FastConnect V3 (REST `securitiesSummary`). GitHub Actions cập nhật sau mỗi phiên (`.github/workflows/ssi-daily.yml`). Vercel đọc file này ở chế độ chỉ đọc. Không chứa khóa API.
