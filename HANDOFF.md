# Bàn giao dự án bộ lọc cổ phiếu VN30 và HNX30

**Ngày cập nhật 06/11/2026.** File này giúp người tiếp quản hiểu đề tài, mở lại bản demo, tìm bằng chứng kiểm thử và tiếp tục tích hợp SSI từ đúng chỗ đang dừng.

**Trạng thái hiện tại:** Đã hoàn thành **7/7 task trong phạm vi offline**. Bộ bàn giao có ứng dụng chạy được, báo cáo PDF, video MP4 và ZIP cài offline. Bản ZIP ngày 05/11/2026 đạt **209/209 kiểm thử** trong môi trường sạch.

**Ngày 06/11/2026:**
- Đề cập nhật (`../261BFF401101_261BFF401102_GPMUD1_DETHICUOIKY_DOAN_CAPNHAT.docx`) chính thức cho phép dùng thêm SSI FastConnect API.
- Đã viết xong bộ nối **FastConnect V3** dùng SDK chính thức `ssi-sdk==3.3.2`: đăng nhập và OTP, REST thành phần nhóm và dữ liệu ngày, WebSocket `trade`/`quote`/`room`/`market.flag`, bộ giải mã, thu theo phiên, đối chiếu stream với REST, đánh giá nhiều phiên.
- Mã nguồn hiện tại đạt **268/268 kiểm thử** offline. ZIP ngày 05/11 **chưa** chứa phần V3.
- **07/11/2026: đã có API Key FastConnect V3** (lưu trong `.env`, profile `fastconnect_v3`). REST thật đã chạy được: 10 phiên × 60 mã (599/600 dòng) vào `runtime/ssi_daily.sqlite`. Phát hiện `securitiesSummary?index=` trả về chính chỉ số nên code đã sửa sang lấy theo từng mã. Đã kiểm chứng giá trị khớp = giá bình quân × khối lượng (trung vị tỷ lệ 1,0000). Stream chưa thử vì sàn nghỉ. `SSI_SEMANTICS_VERIFIED` vẫn `false`. [Kết quả REST thật](evidence/v3_history/KET_QUA_REST_THAT.md)
- Giao diện có nguồn **"Cuối ngày · SSI thật"** (phương pháp `daily-v1`, 3 yếu tố, không có sổ lệnh), chạy được cả ngoài giờ giao dịch trên 10 phiên REST thật.
- Đã chuẩn bị triển khai miễn phí **Vercel + GitHub Actions** (không cần thẻ, máy tắt vẫn chạy): workflow lấy dữ liệu ngày lúc 15:20, Vercel hiển thị. Mã đã đẩy lên [MasonTahieu/CuoiKi](https://github.com/MasonTahieu/CuoiKi) (công khai). Còn thêm GitHub Secrets, chạy thử workflow và import vào Vercel. [Hướng dẫn](docs/TRIEN_KHAI_VERCEL.md)
- Khóa đã từng được dán vào chat. Nên thu hồi và tạo khóa mới trên Developer Portal, rồi tự điền vào `.env`.
- Hướng dẫn khi có khóa: [docs/V3_KET_NOI.md](docs/V3_KET_NOI.md).

## Đề tài và mục đích

**Tên đề tài:** Xây dựng hệ thống sàng lọc và xếp hạng cổ phiếu đa yếu tố trong phiên cho VN30 và HNX30 sử dụng SSI FastConnect, phục vụ nhà đầu tư và môi giới.

Người dùng chọn nhóm và mốc quan sát, xem mã nổi bật theo bốn yếu tố, rồi mở chi tiết để hiểu vì sao một mã có điểm cao, thấp hoặc chưa được xếp hạng. Sản phẩm giúp thu hẹp danh sách cần nghiên cứu. Phạm vi là dữ liệu thị trường cổ phiếu, xếp hạng tương đối trong từng nhóm và chạy theo chế độ chỉ đọc.

Dự án ban đầu hướng tới VN30 và VPBankS NEO API. Đã lấy được token NEO nhưng yêu cầu đọc dữ liệu thị trường trả HTTP 401 với mã `NEOINP000401`. Theo xác nhận của người học, giảng viên đã đồng ý đổi nguồn sang SSI FastConnect. Phạm vi hiện tại gồm hai nhóm VN30 và HNX30. Thư mục mã nguồn vẫn mang tên `neo-vn30-screener` và giữ nhánh NEO để truy vết. Tên ZIP giữ mẫu `MSSV_HoTen_NEOAPI_FinTech.zip` theo quy cách đề. [Đề gốc](../261BFF401101_261BFF401102_GPMUD1_DETHICUOIKY_DOAN.docx) · [Kế hoạch SSI](../KE_HOACH_BO_LOC_VN30_HNX30_SSI.md) · [Tiến độ chi tiết](../TIEN_DO_DU_AN.md)

## Tiến trình đã làm

| Task | Kết quả đã có | Đọc tiếp |
|---|---|---|
| 1. Giải mã SSI | Chuẩn hóa các bản tin F, X, X-Quote, X-Trade, R và B theo tài liệu FCData v2. Giữ thời điểm nguồn, trường vắng, giá trị null và cờ ước tính khối ngoại. | [Đặc tả](docs/TASK_1_GIAI_MA_SSI.md) · [Mẫu giải mã](evidence/task1/KET_QUA_MAU.md) |
| 2. Thu thập giả lập | Collector nhận gói qua một giao diện kết nối, ghép bản cập nhật theo từng trường, bỏ gói trùng, xử lý mất kết nối và dựng lại dữ liệu nền. Ghi được vào SQLite. | [Đặc tả](docs/TASK_2_COLLECTOR_GIA_LAP.md) · [Mẫu luồng](evidence/task2/KET_QUA_MAU.md) |
| 3. SQLite, phát lại và chất lượng | Ghi theo lô, đọc theo nguồn, lần thu thập và mốc hoặc ID sự kiện. Kiểm tra trường thiếu, cũ, trễ, lỗi kiểu dữ liệu, khoảng gián đoạn và độ phủ. Đã sửa thông báo cho bản ghi giải mã hỏng thiếu trường bắt buộc. | [Đặc tả](docs/TASK_3_LUU_TRU_REPLAY_CHAT_LUONG.md) · [Tám mốc mẫu](evidence/task3/KET_QUA_MAU.md) |
| 4. Bốn yếu tố và điểm | Kiểm chứng tính tay, phân vị, đồng hạng, ngưỡng nhóm, hai bộ trọng số và hai cách tính khối ngoại. | [Công thức](docs/TASK_4_KIEM_CHUNG_BON_YEU_TO.md) · [Kết quả mẫu](evidence/task4/KET_QUA_MAU.md) |
| 5. Giao diện | Bảng điểm và nhật ký SSI mẫu, bộ lọc theo nhóm/mã, chi tiết từng yếu tố, biểu đồ cột và đường, dấu thời gian, lý do chưa xếp hạng, làm mới kho và CSV kèm cấu hình. | [Hướng dẫn thử](docs/TASK_5_GIAO_DIEN.md) |
| 6. Kiểm thử toàn tuyến | Chạy từ gói SSI giả lập qua SQLite đến bảng điểm và CSV. Thử mất kết nối, xác thực, timeout, REST 429/503/403 và dữ liệu ngày. Sửa ba lỗi ở trạng thái kết nối, bản ghi REST sai kiểu và vô hiệu hóa token khi gặp 401. | [Ma trận T01–T24](docs/TASK_6_KIEM_THU_TOAN_TUYEN.md) · [Kết quả pytest](evidence/task6-tests.xml) |
| 7. Báo cáo và gói chạy | PDF 11 trang, MP4 khoảng 32 giây, kịch bản demo và ZIP có thư viện cài offline. Đã kiểm lại T24 trên đúng bản ZIP bàn giao. Họ tên, MSSV và mã lớp trên bìa được để trống theo yêu cầu. | [Biên bản kiểm tra](evidence/task7/KIEM_TRA_GOI.md) · [Kịch bản demo](report/KICH_BAN_DEMO.md) |
| 9. Giao diện web mới (06/11) | Thay Streamlit bằng dashboard nền tối theo chuẩn ngành (tham chiếu SSI iBoard, FireAnt/Simplize), do người học chọn. Python thư viện chuẩn phục vụ JSON, HTML/CSS/JS tự viết, chạy offline. Bảng xếp hạng có thanh đóng góp và thanh phân vị từng yếu tố, khung giải thích mã, mỗi mã một nhãn trạng thái. 8 ca kiểm thử API/server. Có so sánh hạng và điểm với mốc trước (mũi tên cạnh hạng, dòng so sánh trong khung giải thích, vạch điểm cũ trên biểu đồ). | [PRODUCT.md](PRODUCT.md) · [Hợp đồng thiết kế](.impeccable/surfaces/src-web-static-index-html.md) |
| 8. Bộ nối FastConnect V3 (06/11) | Client đăng nhập và REST, adapter WebSocket bọc SDK, bộ giải mã V3 dùng chung bản ghi nội bộ với v2, chính sách chất lượng riêng cho V3 (không có trạng thái từng mã, suy phiên theo lịch khi thiếu cờ), smoke test, thu theo khung giờ, lịch sử 10 phiên, đánh giá nhiều phiên. 43 ca kiểm thử mới, gồm phát lại nhật ký V3 trên Streamlit. | [Hướng dẫn V3](docs/V3_KET_NOI.md) · [Nháp bổ sung báo cáo](report/BO_SUNG_BAO_CAO_V3.md) |

## Phương pháp chấm điểm

| Yếu tố | Cách tính |
|---|---|
| Động lượng | `100 × (giá khớp gần nhất / giá mở cửa − 1)` |
| Thanh khoản | Trung bình phân vị của tổng giá trị khớp, độ sâu sổ lệnh ba mức mỗi bên và chênh lệch giá mua bán tốt nhất. Chênh lệch hẹp hơn được điểm cao hơn. |
| Dòng tiền ngoại tương đối | Mặc định dùng `(giá trị ngoại mua − bán) / tổng giá trị khớp` cùng phạm vi. Có cấu hình đối chiếu riêng theo khối lượng. |
| Mất cân bằng cung cầu | `(tổng lượng chào mua − tổng lượng chào bán) / tổng lượng chào hai bên`, lấy ba mức mỗi bên. |

Điểm từng yếu tố là phân vị 0–100 trong nhóm hợp lệ tại cùng mốc. Tổng điểm dùng trọng số **25/25/25/25**, hoặc **40/20/20/20** khi ưu tiên động lượng. Điểm hòa nhận cùng hạng. Mỗi nhóm cần **ít nhất 10 mã hợp lệ**. Dữ liệu thiếu, quá cũ, ngoài phiên liên tục LO hoặc thiếu xác minh nguồn thật có thể khiến mã chưa được chấm. Bộ lọc mã và ngưỡng điểm trên giao diện áp dụng sau khi tính hạng.

CSV giữ nhóm, nguồn, lần thu thập, mốc, mã phương pháp, mã cấu hình và mã tập so sánh. Các trường này giúp phân biệt việc hạng đổi do đổi trọng số, đổi dữ liệu hoặc đổi tập mã đủ điều kiện. [Quy tắc xếp hạng và cấu hình](docs/TASK_4_KIEM_CHUNG_BON_YEU_TO.md)

## Kiến trúc và chỗ cần tìm trong mã nguồn

```text
Nguồn dữ liệu → Giải mã và thu thập → Nhật ký SQLite
             → Phát lại và kiểm tra chất lượng → Tính yếu tố và xếp hạng → UI / CSV
```

| Vị trí | Vai trò |
|---|---|
| `src/ssi_api/` | Profile SSI, REST v2, decoder v2/V3, collector và công cụ phát lại. V3: `v3_client.py` (đăng nhập và REST), `v3_stream.py` (WebSocket), `v3_decoder.py`, `v3_ops.py` (smoke, thu phiên, lịch sử, đối chiếu), `v3_sample.py` (gói tin giả lập). `stream_collector.py` chọn bộ giải mã theo profile. |
| `src/analytics/sessions.py` | Đánh giá nhiều phiên: độ phủ theo mốc, Spearman giữa các mốc và giữa các cấu hình, khoảng cập nhật để chọn ngưỡng dữ liệu cũ, độ bền yếu tố theo ngày. |
| `SSI_V3.ps1` | Năm lệnh `kiemtra`, `smoke`, `lichsu`, `phien`, `danhgia`. |
| `src/data/` | Lưu và đọc SQLite, chuẩn hóa, chất lượng và tạo dữ liệu giả lập. |
| `src/finance/factors.py`, `src/ranking/engine.py` | Bốn yếu tố, phân vị, trọng số, ngưỡng hợp lệ và xếp hạng. |
| `src/web/` | Giao diện chính từ 06/11: `server.py` (HTTP thư viện chuẩn, chỉ 127.0.0.1), `api.py` (JSON từ pipeline sẵn có), `static/` (HTML/CSS/JS). Chạy bằng `RUN_APP.ps1`. |
| `app.py`, `src/app/` | Giao diện Streamlit cũ, giữ làm dự phòng (`RUN_APP.ps1 -Streamlit`). |
| `src/cli.py` | Kiểm tra cấu hình, chạy bảng điểm demo và thu thập REST. |
| `tests/`, `evidence/`, `report/` | Ca kiểm thử tự động, bằng chứng kết quả, kịch bản demo và tài liệu báo cáo. |
| `.env.example`, `requirements-win-py313.lock.txt` | Cấu hình mẫu trống và 46 phụ thuộc đã khóa cho Windows x64, CPython 3.13 (đã thêm `ssi-sdk`, `httpx`, `httpcore`). |

Kho SSI mặc định là `runtime/ssi.sqlite`. Lệnh demo bảng điểm tạo `runtime/synthetic.sqlite` và `runtime/synthetic_ranking.csv`. Lệnh tạo nhật ký mẫu ghi `runtime/task3-synthetic.sqlite`. Hai nhật ký dựng từ giao diện demo nằm ở kho tạm. Nguồn, lần thu thập và phiên kết nối được theo dõi riêng. Thời điểm lưu và hiển thị theo giờ Việt Nam UTC+7.

## Mở lại và kiểm tra nhanh

Mở PowerShell tại thư mục chứa `app.py`. Trong ZIP có sẵn thư viện cài offline cho **Windows x64 và CPython 3.13**. Chạy lệnh cài khi môi trường chưa có thư viện, rồi mở ứng dụng.

```powershell
.\CAI_THU_VIEN.ps1
.\RUN_APP.ps1
```

Giao diện web chạy cục bộ tại `http://127.0.0.1:8501` (thêm `-Streamlit` để mở giao diện cũ). Mặc định `DATA_PROVIDER=ssi` và `APP_MODE=demo`. Các lệnh dùng môi trường chung `~/.venv` theo mặc định. Truyền cùng `-VenvPath` cho các script nếu cần dùng một môi trường Python 3.13 khác. [README](README.md)

- **Bảng điểm giả lập:** 24 mã hư cấu, 12 mã mỗi nhóm, 75 sự kiện. Thử chọn nhóm, đổi trọng số, lọc mã và xuất CSV.
- **Nhật ký SSI mẫu:** 2 mã hư cấu để minh họa chất lượng. Chọn lần **Mất kết nối và phục hồi**, xem mốc 10:00:06 rồi 10:00:13. Chọn lần **Dữ liệu khối ngoại cũ** để xem tuổi nguồn 63 giây vượt ngưỡng thử nghiệm 60 giây. [Hướng dẫn giao diện](docs/TASK_5_GIAO_DIEN.md)
- **Kiểm chứng toàn tuyến:** bộ riêng 22 mã hư cấu, 11 mã mỗi nhóm. Khi VN30 còn 9 mã hợp lệ, nhóm này dừng xếp hạng còn HNX30 vẫn xếp 11 mã. Ca HOSETEST11 lên từ 55 điểm/hạng 4 đến 64 điểm/hạng 1 khi đổi trọng số. Đây là kết quả trên dữ liệu dựng để kiểm thử. [Kết quả toàn tuyến](docs/TASK_6_KIEM_THU_TOAN_TUYEN.md)

```powershell
.\CHECK_PROJECT.ps1
& "$HOME\.venv\Scripts\Activate.ps1"
python -X utf8 -m src.cli readiness
python -X utf8 -m src.cli demo-pipeline
python -X utf8 -m src.ssi_api.replay_sample
python -X utf8 -m src.ssi_api.replay --db runtime/task3-synthetic.sqlite --list-runs
```

Các lệnh trên kiểm tra cấu hình, chạy demo và phát lại mẫu cục bộ. Chế độ `APP_MODE=replay` cho chọn lần thu thập và mốc trong kho. Chế độ `APP_MODE=live` đọc kho đã có theo giờ hiện tại và có thể làm mới mỗi 10 hoặc 30 giây. Việc thu dữ liệu vào kho thuộc về collector.

## Bộ hồ sơ bàn giao

Ba tệp nằm trong thư mục `Bo_nop_VN30_HNX30_SSI` cạnh thư mục dự án.

| Tệp | Nội dung |
|---|---|
| [Gói mã nguồn ZIP](../Bo_nop_VN30_HNX30_SSI/MSSV_HoTen_NEOAPI_FinTech.zip) | Khoảng 90 MB, gồm mã nguồn, thư viện cài offline, cấu hình mẫu, hướng dẫn chạy, kiểm thử và bằng chứng giả lập. |
| [Báo cáo PDF](../Bo_nop_VN30_HNX30_SSI/MSSV_HoTen_BaoCao.pdf) | 11 trang gồm bìa, 9 trang nội dung và phụ lục. Ba trường thông tin trên bìa để trống. |
| [Video MP4](../Bo_nop_VN30_HNX30_SSI/MSSV_HoTen_Demo.mp4) | Khoảng 32 giây, sáu cảnh có phụ đề, từ bảng điểm đến phát lại và cảnh báo chất lượng. |

Bản ZIP được nghiệm thu ngày 05/11/2026. Gói không kèm tệp `.env` cá nhân, khóa API, kho SQLite vận hành hay lịch sử Git. File HANDOFF này là ghi chú bàn giao bổ sung trong thư mục mã nguồn. [Biên bản và SHA-256](evidence/task7/KIEM_TRA_GOI.md)

## Công việc còn lại

**Người học làm:**
1. Gọi 1900545471 hoặc đến chi nhánh SSI để đăng ký **FastConnect API** (dữ liệu thị trường HOSE/HNX, REST và streaming). Hỏi luôn: stream có bắt buộc OTP không, và hạn mức REST là bao nhiêu.
2. Tạo API Key/Secret trên Developer Portal, điền vào `.env` theo `.env.example`. Không dán khóa vào chat.
3. Hỏi giảng viên một câu để xác nhận dùng SSI làm nguồn cốt lõi duy nhất là được, vì đề viết "bổ sung".

**Khi có khóa** (chi tiết trong [docs/V3_KET_NOI.md](docs/V3_KET_NOI.md)):
1. `.\SSI_V3.ps1 -Lenh smoke -Giay 60` trong giờ giao dịch. Sửa bộ giải mã nếu định dạng thật khác giả định, rồi chạy lại test.
2. `.\SSI_V3.ps1 -Lenh lichsu -SoPhien 10` để có ngay dữ liệu ≥ 5 phiên.
3. `.\SSI_V3.ps1 -Lenh phien` mỗi ngày giao dịch, ít nhất 5 ngày.
4. `.\SSI_V3.ps1 -Lenh danhgia`, chọn ngưỡng dữ liệu cũ từ phân vị khoảng cập nhật, chốt cách tính khối ngoại.
5. Bật `SSI_SEMANTICS_VERIFIED=true` khi đạt các điều kiện ở mục 4 của hướng dẫn V3.
6. Điền [bản nháp bổ sung báo cáo](report/BO_SUNG_BAO_CAO_V3.md) vào báo cáo. Quay lại video với dữ liệu thật. Điền họ tên, MSSV, mã lớp và đổi tên tệp nộp.
7. Đóng gói lại ZIP: thêm wheel `ssi-sdk`, `httpx`, `httpcore` vào thư mục cài offline, cài lại trong môi trường sạch, chạy toàn bộ test. Kiểm tra lại để chắc `.env` không nằm trong gói.

**Điểm chưa chắc chắn, chỉ kiểm được bằng dữ liệu thật:**
- dạng thời gian `t`;
- giá trị thật của cờ phiên;
- tổng giá trị khớp suy ra (`a × v`) có khớp REST hay không;
- giá trị ngoại là số chính xác hay số ước tính;
- server có gửi snapshot khi vừa đăng ký topic hay không;
- quyền đăng ký topic theo rổ (`trade.VN30@*`).
