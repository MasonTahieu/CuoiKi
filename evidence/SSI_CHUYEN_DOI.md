# Kiểm tra chuyển nền sang SSI — 04/11/2026

- Người học xác nhận giảng viên đồng ý đổi nguồn; hiện chưa đăng ký SSI.
- Mặc định SSI, profile unselected; chỉ đọc đúng nguồn cấu hình, không dùng token NEO cho SSI.
- Mock FCData v2: auth, nested IndexComponents HNX30, kiểm tra tổng và sàn, chặn endpoint ngoài thị trường.
- Ghi/đọc nguồn SSI và lọc khóa nhạy cảm; DailyStockPrice không tạo giả sổ lệnh/phiên.
- Dựng và xếp hạng hai nhóm độc lập, cổng xác minh SSI thật hoạt động.
- Streamlit AppTest chuyển HNX30 và hiển thị đúng 12 mã hư cấu, không trộn nhóm.
- **63 passed trong 6,61 giây**. XML: ssi-migration-tests.xml.
- Demo CLI: **24 mã hư cấu, 75 sự kiện, 24 kết quả có hạng** chia riêng hai nhóm.
- Readiness: provider=ssi, thiếu SSI_API_PROFILE như kỳ vọng; không gọi mạng.

Đây là kết quả phần mềm offline. Chưa gọi SSI thật, chưa cài SDK SSI và chưa triển khai collector streaming/V3.
Thực hiện tiếp theo dịch vụ được SSI cấp và ghi rõ hạn chế khối ngoại ước tính.
