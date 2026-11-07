# Chuẩn bị đường dẫn FastConnect — 04/11/2026

Đối chiếu guide và source chính thức SSI: config.py, model/api.py, fc_md_client.py, fc_md_stream.py.
Xác nhận hợp đồng FCData v2 REST api/v2/Market và SignalR v2.0/signalr, FcMarketDataV2Hub/Broadcast/SwitchChannels.
Tách các địa chỉ V3 có tài liệu xác nhận, giữ các collector chưa viết ở trạng thái chưa triển khai.
Đường dẫn runtime ở src/ssi_api/connections.py; JSON config/ssi_connection_profiles.json là bản xuất để đọc.
SSI_REST_BASE kiểm tra HTTPS/host/path trước khi client giữ khóa; không tự fallback URL.
SSI_STREAM_BASE là trường dự trữ, chưa kích hoạt kết nối.

Kiểm thử toàn bộ: 71 passed trong 8,63 giây, XML ssi-connection-tests.xml.
Readiness: provider SSI, thiếu profile như kỳ vọng, network_called=false.
Chưa cài SDK và chưa gửi yêu cầu có khóa tới SSI. Công việc S02–S08 còn lại được liệt kê, chưa triển khai trong lần đọc tài liệu này.
