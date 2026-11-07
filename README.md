# Bộ lọc VN30 và HNX30 đa yếu tố — SSI FastConnect

Cập nhật **06/11/2026**: đề cập nhật cho phép dùng thêm SSI FastConnect API (developers.ssi.com.vn).
Đã có bộ nối **FastConnect V3** dùng SDK chính thức `ssi-sdk==3.3.2`, kiểm thử offline với gói tin giả lập.
Hiện **chưa có khóa SSI**, nên chưa nghiệm thu dữ liệu thật. Khi có khóa, làm theo [hướng dẫn V3](docs/V3_KET_NOI.md).

- [Kết nối FastConnect V3](docs/V3_KET_NOI.md)
- [Triển khai miễn phí lên Vercel + GitHub Actions](docs/TRIEN_KHAI_VERCEL.md) · Repo: [MasonTahieu/CuoiKi](https://github.com/MasonTahieu/CuoiKi)
- [Đăng ký SSI và phạm vi chuyển đổi](docs/CHUYEN_SANG_SSI.md)
- [Ghi chú bàn giao và tiến độ](HANDOFF.md)

## Chạy nhanh từ gói nộp

Dùng **CPython 3.13 x64 trên Windows**. Giải nén toàn bộ gói rồi mở PowerShell tại thư mục chứa `app.py`.

```powershell
.\CAI_THU_VIEN.ps1
.\RUN_APP.ps1
```

Gói có bộ thư viện cài offline và tệp khóa phiên bản. Cả hai lệnh dùng môi trường chung `~/.venv` mặc định. Nếu máy đã có môi trường Python 3.13 khác, truyền cùng tham số `-VenvPath` cho hai lệnh để chọn vị trí đó. Dùng `.\CHECK_PROJECT.ps1` để chạy kiểm tra và toàn bộ bộ test.

Giao diện mở tại `http://127.0.0.1:8501`. Chế độ demo dùng cấu hình mặc định và dữ liệu giả lập dựng từ mã nguồn. [Cách thử hai màn hình demo](docs/TASK_5_GIAO_DIEN.md) · [Kịch bản trình diễn](report/KICH_BAN_DEMO.md)

## Task 6 đã bàn giao

Đã kiểm tra từ gói SSI giả lập qua SQLite đến bảng điểm và CSV, gồm tình huống thiếu dữ liệu, mất kết nối, lỗi adapter và hết hạn xác thực. Toàn dự án đạt 209 kiểm thử. [Ma trận T01–T24 và cách chạy lại](docs/TASK_6_KIEM_THU_TOAN_TUYEN.md)

## Task 5 đã bàn giao

Trong chế độ demo, mục **Dữ liệu minh họa** chuyển giữa bảng điểm và nhật ký SSI mẫu. Nhật ký có lựa chọn lần thu thập và mốc phát lại, trạng thái kết nối, độ mới từng cụm dữ liệu và lý do chưa xếp hạng. [Hướng dẫn thử giao diện](docs/TASK_5_GIAO_DIEN.md)

## Task 4 đã bàn giao

Đã đối chiếu bốn yếu tố bằng ca tính tay, so sánh hai cách tính khối ngoại và đo mức đổi hạng khi đổi trọng số trên 22 mã giả lập. Toàn dự án đạt 191 kiểm thử. [Kết quả mẫu](evidence/task4/KET_QUA_MAU.md) · [Đặc tả kiểm chứng](docs/TASK_4_KIEM_CHUNG_BON_YEU_TO.md)

```powershell
& "$HOME\.venv\Scripts\Activate.ps1"
python -X utf8 -m src.ranking.verify_factors
```

## Task 3 đã bàn giao

Đã có lưu SQLite theo lô, phát lại theo thời điểm/event ID và báo cáo dữ liệu thiếu/cũ/trễ,
độ phủ từng nhóm, mất kết nối và trạng thái từng mã.
Xem [bảng mẫu tám mốc task 3](evidence/task3/KET_QUA_MAU.md) và [hướng dẫn task 3](docs/TASK_3_LUU_TRU_REPLAY_CHAT_LUONG.md).

```powershell
& "$HOME\.venv\Scripts\Activate.ps1"
python -X utf8 -m src.ssi_api.replay_sample
python -X utf8 -m src.ssi_api.replay --db runtime/task3-synthetic.sqlite --list-runs
```

Lệnh tạo kho mẫu riêng. Giao diện ở task 5 đọc cùng định dạng journal. Kết quả pytest ở thời điểm bàn giao task 3 gồm 181 ca.

## Task 2 đã bàn giao

Collector giả lập đã có ghép patch, timestamp từng trường, chống trùng và xử lý ngắt/kết nối lại.
Xem [bảng mẫu task 2](evidence/task2/KET_QUA_MAU.md) và [hợp đồng collector](docs/TASK_2_COLLECTOR_GIA_LAP.md).

```powershell
& "$HOME\.venv\Scripts\Activate.ps1"
python -X utf8 -m src.ssi_api.collect_sample
```

Kho task 2 tách riêng và có thể phát lại bằng công cụ task 3 hoặc giao diện task 5.

## Task 1 đã bàn giao

Bộ giải mã FCData v2 đã hoàn thành offline và được collector task 2 sử dụng.
Xem [bảng mẫu để kiểm tra](evidence/task1/KET_QUA_MAU.md) và [hợp đồng decoder](docs/TASK_1_GIAI_MA_SSI.md).

```powershell
& "$HOME\.venv\Scripts\Activate.ps1"
python -X utf8 -m src.ssi_api.decode_sample
```

## Chạy ngay

```powershell
.\RUN_APP.ps1
```

Từ 06/11/2026, `RUN_APP.ps1` mở **giao diện web mới** tại http://127.0.0.1:8501. Server là Python thư viện chuẩn (`src/web/server.py`), giao diện là HTML/CSS/JS tự viết (`src/web/static/`), chạy offline, không cần cài thêm gói. Giao diện Streamlit cũ vẫn mở được bằng `.\RUN_APP.ps1 -Streamlit`.

Giao diện mới là dashboard nền tối theo chuẩn các ứng dụng chứng khoán Việt:
- thanh trên cùng có nhóm VN30/HNX30, trạng thái kết nối và mốc phân tích;
- bốn chỉ số tổng quan;
- bảng xếp hạng: thanh điểm tổng chia theo phần đóng góp, mỗi yếu tố có thanh phân vị riêng, mỗi mã có một nhãn trạng thái;
- khung bên phải giải thích vì sao mã đứng hạng đó, kèm đường giá đã ghi nhận và biểu đồ điểm tổng của cả nhóm;
- hai tab Chất lượng dữ liệu và Phương pháp.
- so sánh với một mốc trước (mặc định mốc dữ liệu liền trước; chọn được 30 giây, 1, 5, 15 phút hoặc tắt): mũi tên và số bậc thay đổi cạnh hạng, chênh hạng và chênh điểm trong khung giải thích, vạch trắng đánh dấu điểm cũ trên biểu đồ. CSV ghi thêm `compare_as_of`, `prev_rank`, `rank_change`, `total_change`.

Trạng thái màn hình (nguồn, lần thu thập, mốc, nhóm, trọng số, mã đang chọn) nằm trên URL, nên một kết quả có thể mở lại đúng như cũ.

Nguồn **"Cuối ngày · SSI thật"** xuất hiện ở mọi chế độ khi đã có `runtime/ssi_daily.sqlite` (tạo bằng `.\SSI_V3.ps1 -Lenh lichsu`). Nguồn này xếp hạng theo dữ liệu tổng hợp từng phiên của SSI, dùng được cả ngoài giờ giao dịch. Đây là phương pháp riêng `daily-v1` với 3 yếu tố: động lượng đóng cửa so với mở cửa, thanh khoản theo giá trị khớp, dòng tiền ngoại; trọng số 33/33/33 hoặc 50/25/25. Không có sổ lệnh nên không có cung–cầu. Mã thiếu dữ liệu khối ngoại không được xếp hạng.

Mặc định DATA_PROVIDER=ssi, APP_MODE=demo. Chế độ demo có hai nguồn:
- **bảng điểm giả lập**: 24 mã hư cấu;
- **nhật ký SSI mẫu**: V3 và FCData v2, có các tình huống mất kết nối, dựng lại dữ liệu nền và dữ liệu khối ngoại cũ.
Các mã không phải thành phần thật của chỉ số. Chọn nhóm xác định nhóm so sánh; lọc mã/điểm không tính lại điểm.

```powershell
& "$HOME\.venv\Scripts\Activate.ps1"
python -X utf8 -m src.cli readiness
python -X utf8 -m src.cli connection-plan
python -X utf8 -m src.cli demo-pipeline
python -X utf8 -m pytest -q
```

Demo lưu runtime/synthetic.sqlite, run synthetic-two-groups-v1; bảng xuất runtime/synthetic_ranking.csv.
Nguồn SSI mặc định lưu runtime/ssi.sqlite, NEO cũ runtime/neo.sqlite. Không trộn nguồn hoặc dùng token chéo nguồn.

## Cấu hình

Xem .env.example. Không ghi đè .env hiện có hoặc gửi khóa vào chat.
Biến môi trường ưu tiên hơn .env tại gốc dự án; không tìm .env ở thư mục cha.

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| DATA_PROVIDER | ssi | ssi hoặc neo (nhánh cũ) |
| APP_MODE | demo | demo/replay/live |
| SSI_API_PROFILE | unselected | Chọn phiên bản sau khi đăng ký được cấp |
| SSI_CONSUMER_ID / SSI_CONSUMER_SECRET | Trống | FCData v2 (dự phòng) |
| SSI_API_KEY / SSI_API_SECRET | Trống | FastConnect V3 |
| SSI_CLIENT_ID | Trống | Chỉ điền nếu SSI cấp kèm |
| SSI_OTP_MODE | prompt | prompt/smart/none khi đăng nhập V3 |
| SSI_V3_SUBSCRIBE | index | index (`trade.VN30@*`) hoặc symbols (từng mã) |
| SSI_DATABASE | runtime/ssi.sqlite | Kho đúng nguồn |
| SSI_SEMANTICS_VERIFIED | false | Khóa chấm điểm thật đến khi kiểm chứng |

Với `SSI_API_PROFILE=fastconnect_v3`, script `SSI_V3.ps1` chạy năm lệnh:

| Lệnh | CLI | Gọi mạng | Việc làm |
|---|---|---|---|
| `-Lenh kiemtra` | `readiness` | Không | Kiểm tra cấu hình và SDK |
| `-Lenh smoke -Giay 60` | `smoke-v3` | Có | Đăng nhập, đọc thành phần nhóm và dữ liệu ngày, stream ngắn, ghi `evidence/v3_smoke` |
| `-Lenh lichsu -SoPhien 10` | `history-v3` | Có, REST | Lưu 10 phiên `securitiesSummary` vào `runtime/ssi_daily.sqlite` |
| `-Lenh phien` | `session-v3` | Có | Thu 08:58–11:31 và 12:59–14:46, đối chiếu REST lúc 15:05 |
| `-Lenh danhgia` | `evaluate-v3` | Không | Đánh giá nhiều phiên, ghi `evidence/v3_sessions/evaluation.json` |

FCData v2 vẫn có `collect --transport rest` làm dự phòng. Streaming chỉ có cho V3.

`replay` đọc journal SSI cục bộ và cho chọn lần thu thập, mốc phát lại. `live` đọc kho đúng nhà cung cấp theo giờ hiện tại, với nút đọc lại và tùy chọn 10 hoặc 30 giây. Giao diện chỉ đọc kho, còn collector đảm nhiệm kết nối.
Nhánh NEO cũ nằm riêng trong `src/neo_api`.

## Môi trường và cấu trúc

Môi trường kiểm thử của gói là Python 3.13.15 trên Windows x64. `requirements.txt` liệt kê phụ thuộc trực tiếp, còn `requirements-win-py313.lock.txt` ghi phiên bản của toàn bộ 46 thư viện dùng để cài lại (đã thêm `ssi-sdk`, `httpx`, `httpcore`). Từ 07/11/2026, `requirements.txt` là bộ gọn cho Vercel/CI; bộ đầy đủ cho máy cá nhân nằm ở `requirements-local.txt`.

```text
src/ssi_api/      Cấu hình, REST v2, client/decoder/stream V3, collector, replay SSI
src/analytics/    Đánh giá nhiều phiên: độ phủ, độ ổn định hạng, khoảng cập nhật
src/neo_api/      Nhánh NEO cũ, giữ để truy vết
src/providers.py  Chọn cấu hình nguồn
src/data/         Store, ghi lô/đọc journal SSI, chất lượng, replay và demo hai nhóm
src/finance/      Bốn yếu tố thô
src/ranking/      Điểm và hạng riêng theo index_group
src/web/          Giao diện web: server.py (thư viện chuẩn), api.py (JSON), static/ (HTML/CSS/JS)
src/app/          Giao diện Streamlit cũ, giữ làm dự phòng
runtime/          Dữ liệu/CSV cục bộ loại khỏi Git
```

Bốn yếu tố: động lượng từ mở cửa; thanh khoản từ giá trị khớp, spread, độ sâu; ngoại ròng tương đối;
mất cân bằng khối lượng ba mức. Tối thiểu 10 mã hợp lệ trong **mỗi nhóm**, điểm hòa có cùng hạng.
Trọng số cân bằng/ưu tiên động lượng là baseline. Cần đánh giá lại ngữ nghĩa khối ngoại SSI và dữ liệu nhiều phiên.
Điểm chỉ hỗ trợ sàng lọc, chưa có kiểm định dự báo. Không triển khai giao dịch tiền thật.

Bản đồ NEO và các bằng chứng cũ giữ làm lịch sử; tài liệu hiện hành là kế hoạch SSI và docs/CHUYEN_SANG_SSI.md.
