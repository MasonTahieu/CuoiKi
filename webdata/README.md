# Dữ liệu cho bản triển khai web

`ssi_daily.sqlite`: dữ liệu tổng hợp từng phiên của 30 mã VN30 (và dòng chỉ số VN30) lấy từ SSI FastConnect V3 (REST `securitiesSummary`). GitHub Actions cập nhật sau mỗi phiên (`.github/workflows/ssi-daily.yml`). Vercel đọc file này ở chế độ chỉ đọc. Không chứa khóa API.

Dashboard sử dụng dữ liệu SSI của từng phiên để tính hạng. Khi SSI trả trống dữ liệu khối ngoại, dashboard vẫn hiển thị giá và thanh khoản đã thu được. Mã giữ trạng thái chưa xếp hạng ở phiên thiếu dữ liệu và có thể được chấm ở các phiên sau khi dữ liệu của phiên đó đầy đủ.
