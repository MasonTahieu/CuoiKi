# Triển khai miễn phí: Vercel + GitHub Actions

Sau khi làm theo hướng dẫn này, hệ thống vẫn chạy khi máy bạn tắt và không cần thẻ:

```text
GitHub Actions (15:20, thứ Hai–thứ Sáu)
   └─ lấy dữ liệu ngày của 30 mã VN30 từ SSI (REST, không cần OTP) ─▶ commit webdata/ssi_daily.sqlite
                                                                    │ push
Vercel (tự triển khai lại khi có commit) ◀──────────────────────────┘
   └─ trang web: Cuối ngày · SSI thật (mặc định) · Minh họa: Bảng điểm giả lập, Nhật ký SSI mẫu
```

| Tệp | Vai trò |
|---|---|
| `api/index.py` | Hàm Python trên Vercel. Dùng lại đúng bộ xử lý của `src/web/server.py` |
| `vercel.json` | Chuyển mọi đường dẫn về hàm trên; đóng gói `src/` và `webdata/` |
| `requirements.txt` | Phụ thuộc gọn cho Vercel và CI: pandas, numpy, python-dotenv, requests, tzdata |
| `requirements-ci.txt` | Thêm `ssi-sdk` cho workflow lấy dữ liệu |
| `requirements-local.txt` | Bộ đầy đủ cho máy cá nhân (Streamlit, pytest, SDK) |
| `.python-version` | Python 3.12 trên Vercel |
| `.vercelignore` | Không đưa `.env`, `runtime/`, test, tài liệu và giao diện Streamlit lên Vercel |
| `.github/workflows/ssi-daily.yml` | Lịch lấy dữ liệu ngày, đánh giá nhiều phiên, commit kết quả |
| `webdata/ssi_daily.sqlite` | Dữ liệu ngày thật (đã có sẵn 10 phiên từ 26/10 đến 06/11) |

## Bước 0. Nên làm trước

1. **Thu hồi khóa SSI cũ và tạo khóa mới** trên Developer Portal, vì khóa cũ đã được dán vào chat. Sửa `SSI_API_KEY` và `SSI_API_SECRET` trong `.env` trên máy.
2. Tạo tài khoản [GitHub](https://github.com) và đăng nhập [Vercel](https://vercel.com) bằng chính tài khoản GitHub đó. Cả hai miễn phí, không cần thẻ.

## Bước 1. Repo trên GitHub (đã xong)

Repo: [MasonTahieu/CuoiKi](https://github.com/MasonTahieu/CuoiKi), nhánh `main`, đang để **công khai**.

| | Công khai (hiện tại) | Riêng tư |
|---|---|---|
| Ai xem được mã và `webdata/` | Mọi người | Chỉ bạn và người được mời |
| Phút GitHub Actions | Không giới hạn, đủ cho thu stream cả phiên sau này | 2.000 phút/tháng, chỉ đủ cho job cuối ngày |
| Dữ liệu SSI | Công khai trong repo; điều khoản FastConnect cấp dữ liệu cho chủ tài khoản | Không lộ ra ngoài |

Đổi chế độ: **Settings → General → Danger Zone → Change repository visibility**. Khóa SSI nằm trong GitHub Secrets nên không lộ ở chế độ nào.

## Bước 2. Đẩy mã nguồn lên (đã xong)

Lần đầu đã được đẩy lên từ máy này. Đã kiểm 177 tệp: không có `.env`, không có `runtime/`, không tệp nào chứa giá trị khóa trong `.env`.

Thư mục dự án thuộc một tài khoản Windows khác, nên git báo `dubious ownership`. Khi tự chạy git tại đây, thêm ngoại lệ một lần:

```powershell
git config --global --add safe.directory "E:/Gói phần mềm 1/Cuối kì/neo-vn30-screener"
```

Sau đó, mỗi lần sửa mã: `git add .`, kiểm `git status` không có `.env`, rồi `git commit` và `git push`. Trước khi push nên chạy `git pull --rebase`, vì workflow hằng ngày cũng commit dữ liệu lên `main`.

## Bước 3. Thêm khóa SSI vào GitHub Secrets

Trong repo, vào **Settings → Secrets and variables → Actions → New repository secret** và tạo hai secret:

| Tên | Giá trị |
|---|---|
| `SSI_API_KEY` | API Key (bản mới) |
| `SSI_API_SECRET` | API Secret (bản mới) |

**Không** thêm Private Key. Dự án không dùng khóa đó.

## Bước 4. Chạy thử workflow một lần

1. Mở tab **Actions** của repo; nếu GitHub hỏi thì bấm bật Actions.
2. Chọn workflow **SSI daily summaries**, bấm **Run workflow**.
3. Chờ khoảng 1–2 phút rồi mở log:
   - **Thành công:** bước "Fetch the last 15 sessions" in ra số dòng và số phiên. Nếu có dữ liệu mới, repo sẽ có thêm một commit `data: SSI daily summaries …`.
   - **Lỗi xác thực hoặc 403:** SSI có thể chặn dải IP của GitHub, giống DNSE chặn IP đám mây trong repo tham khảo. Gửi mình đoạn log lỗi; log không chứa khóa.

## Bước 5. Triển khai trên Vercel

1. Trên Vercel, chọn **Add New → Project** và **Import** repo vừa tạo.
2. **Framework Preset:** `Other`. **Root Directory:** để trống (gốc repo). Không cần lệnh build.
3. **Environment Variables:**

   | Tên | Giá trị |
   |---|---|
   | `APP_MODE` | `demo` |
   | `DATA_PROVIDER` | `ssi` |
   | `SSI_DAILY_DATABASE` | `webdata/ssi_daily.sqlite` |

   **Không** đưa khóa SSI lên Vercel. Trang web chỉ đọc dữ liệu đã lưu.
4. Bấm **Deploy**. Xong sẽ có địa chỉ dạng `https://vn30-hnx30-screener.vercel.app`.
5. Mở địa chỉ đó. Trang mở sẵn **Cuối ngày · SSI thật**. Ô **Nguồn** còn hai nguồn minh họa: Bảng điểm giả lập và Nhật ký SSI mẫu (mô hình 4 yếu tố trong phiên và cảnh báo chất lượng).

## Hằng ngày diễn ra thế nào

- **15:20, thứ Hai–thứ Sáu:** GitHub Actions lấy lại 15 phiên gần nhất. Dữ liệu mới được thêm, dữ liệu cũ vẫn giữ. Workflow chạy lại đánh giá nhiều phiên rồi commit.
- **Khoảng 1 phút sau:** Vercel tự triển khai bản mới. Bạn và giảng viên mở địa chỉ là thấy phiên mới nhất.
- **Máy bạn không cần bật.** Repo riêng tư có 2.000 phút Actions miễn phí mỗi tháng; job này dùng khoảng 2 phút mỗi ngày.

## Giới hạn hiện tại

- **Chưa thu stream trong phiên trên GitHub Actions.**
  - Việc này chờ smoke test thứ Hai: định dạng thật, có cần OTP không, quyền đăng ký topic.
  - Thu stream cả ngày dùng khoảng 5 giờ/ngày, vượt hạn mức 2.000 phút/tháng của repo riêng tư. Khi đó cần chuyển repo công khai và mã hóa dữ liệu, hoặc chọn cách khác. Sẽ quyết định sau smoke test.
- **Lịch có thể trễ:** lịch của GitHub có thể chạy muộn vài phút đến vài chục phút. Dữ liệu ngày không bị ảnh hưởng.
- **Một phiên đăng nhập cho mỗi API Key:** tránh chạy lệnh SSI trên máy đúng lúc 15:20.
- **Địa chỉ Vercel là công khai:** ai có địa chỉ đều xem được. Nếu cần, có thể thêm mật khẩu sau.
