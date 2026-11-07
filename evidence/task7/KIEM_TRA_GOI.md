# Biên bản kiểm tra gói nộp offline

Ngày kiểm tra **05/11/2026**. Bản bàn giao gồm mã nguồn, báo cáo PDF và video MP4. Họ tên, MSSV và mã lớp để trống trên bìa theo yêu cầu.

| Kiểm tra | Kết quả |
|---|---|
| ZIP | 153 tệp, giải nén được. Toàn bộ dấu kiểm SHA-256 trong manifest khớp. |
| Môi trường sạch | Cài 43 thư viện từ các wheel trong ZIP vào CPython 3.13 x64 trên Windows với chế độ offline. `pip check` đạt. |
| Chạy lại T24 | `CHECK_PROJECT.ps1` từ thư mục giải nén mới đạt 209 kiểm thử. Lệnh demo xếp hạng đủ 24 mã giả lập và giao diện mở được cả hai chế độ demo. |
| Khởi động | `RUN_APP.ps1` từ bản giải nén khởi động máy chủ Streamlit cục bộ. |
| Dữ liệu đóng gói | Gồm mẫu giả lập và cấu hình mẫu. Đã kiểm tra gói trống khóa API, tệp `.env` cá nhân, kho SQLite vận hành và lịch sử Git. |
| Báo cáo | PDF 11 trang gồm bìa, 9 trang nội dung và phụ lục. Ba trường trên bìa có giá trị trống. |
| Video | MP4 31,8 giây, 1440 × 1008, gồm sáu cảnh có phụ đề từ giao diện đã chạy. Đã phát thử và nhảy tới gần cuối video. |

SHA-256 của ZIP

```text
E7ACAF006E23A5E131D3510E48598B917E61EE45D86AAD61A21217BE9EEA31EE
```

Bằng chứng sử dụng dữ liệu giả lập. Quota, đơn vị, độ phủ và vận hành luồng SSI thật cần đối chiếu sau khi được cấp quyền.

[Gói chạy](../../../Bo_nop_VN30_HNX30_SSI/MSSV_HoTen_NEOAPI_FinTech.zip) · [Báo cáo](../../../Bo_nop_VN30_HNX30_SSI/MSSV_HoTen_BaoCao.pdf) · [Video](../../../Bo_nop_VN30_HNX30_SSI/MSSV_HoTen_Demo.mp4)
