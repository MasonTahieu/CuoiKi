"""Interactive official login; password stays in memory, token is never printed."""
import getpass
import re
import sys
from datetime import datetime, timedelta

import requests
from dotenv import dotenv_values, set_key

from src.config import PROJECT_ROOT
from src.data.store import TZ
from src.neo_api.rest import AuthError

AUTH_URL = "https://external.vpbanks.com.vn/auth/token"


def obtain_token(username, password, session=None):
    if not username.strip() or not password:
        raise AuthError("Cần nhập số lưu ký và mật khẩu.")
    session = session or requests
    try:
        response = session.post(AUTH_URL, json={"username":username.strip(), "password":password},
            headers={"Content-Type":"application/json"}, timeout=(5,20), allow_redirects=False)
    except requests.RequestException:
        raise AuthError("Không kết nối được máy chủ xác thực VPBS. Kiểm tra mạng và thử lại.") from None
    if response.status_code != 200:
        raise AuthError(f"Đăng nhập chưa thành công (HTTP {response.status_code}). Kiểm tra tài khoản hoặc liên hệ VPBS; không tự thử lặp.")
    try:
        body = response.json()
    except ValueError:
        raise AuthError("Máy chủ xác thực trả nội dung không đúng JSON.") from None
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict) or body.get("status") != 1:
        raise AuthError("VPBS chưa xác nhận đăng nhập thành công. Kiểm tra tài khoản và quyền dịch vụ.")
    token = data.get("access_token")
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_.~+/-]+=*", token):
        raise AuthError("Phản hồi thiếu access_token hợp lệ; cần kiểm tra tài liệu xác thực.")
    if str(data.get("token_type", "Bearer")).lower() != "bearer":
        raise AuthError("Loại token khác Bearer; chưa hỗ trợ.")
    expires = data.get("expires_in")
    if type(expires) is not int or expires <= 0:
        expires = None
    return token, expires


def save_token(path, token, device, expires=None):
    values = dotenv_values(path, interpolate=False) if path.exists() else {}
    # Preserve existing app mode and every unrelated setting. Never store username/password/refresh token.
    defaults = {"APP_MODE":"demo", "APP_TIMEZONE":"Asia/Ho_Chi_Minh",
                "NEO_DEVICE_TYPE":"chrome", "NEO_SEMANTICS_VERIFIED":"false"}
    for key, value in defaults.items():
        if not values.get(key):
            set_key(str(path), key, value)
    set_key(str(path), "NEO_ACCESS_TOKEN", token)
    set_key(str(path), "NEO_DEVICE_ID", device)
    expiry = (datetime.now(TZ)+timedelta(seconds=expires)).isoformat() if expires else ""
    set_key(str(path), "NEO_TOKEN_EXPIRES_AT", expiry)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("Đăng nhập NEO · gửi trực tiếp tới https://external.vpbanks.com.vn/auth/token")
    print("Lưu access token vào .env; không lưu mật khẩu, không in token. Không thực hiện giao dịch.")
    if not sys.stdin.isatty():
        print("Hãy mở DANG_NHAP_NEO.cmd trong cửa sổ riêng để nhập thông tin trên máy.")
        return 2
    path = PROJECT_ROOT / ".env"
    try:
        values = dotenv_values(path, interpolate=False) if path.exists() else {}
        device = input("Device ID (Enter để dùng vn30-screener): ").strip() or values.get("NEO_DEVICE_ID") or "vn30-screener"
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", device):
            raise AuthError("Device ID chỉ dùng chữ, số, dấu chấm, gạch dưới hoặc gạch ngang.")
        username = input("Số lưu ký / tên đăng nhập: ").strip()
        print("Mật khẩu bên dưới được ẩn: khi gõ sẽ không hiện ký tự hoặc dấu *. Nhập xong nhấn Enter.")
        password = getpass.getpass("Mật khẩu NEO Invest (ẩn): ")
        token, expires = obtain_token(username,password)
        del password, username
        save_token(path,token,device,expires)
        del token
        print("Đã lấy và lưu token vào .env. Chưa kiểm tra quyền truy cập dữ liệu thị trường.")
        if expires:
            print(f"Thời hạn theo phản hồi: {expires} giây tính từ lần đăng nhập này.")
        return 0
    except AuthError as error:
        print(str(error))
        return 2
    except OSError:
        print("Chưa lưu được token vào .env. Kiểm tra quyền ghi tệp.")
        return 2
    except (KeyboardInterrupt, EOFError):
        print("Đã hủy đăng nhập.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
