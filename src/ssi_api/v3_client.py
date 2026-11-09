"""FastConnect V3 login and read-only market-data REST, on top of the official ``ssi-sdk``.

One ``V3Client`` per process: the server keeps one session per apiKey, so REST and the stream
must share this login. Raw JSON is read (``rest_client.get``) instead of the SDK models, which
turn an omitted number into 0. Only market-data routes are reachable from here.
"""
from datetime import date, datetime
import re

from src.data.daily_store import default_daily_path, known_members
from src.neo_api.rest import AuthError, NeoError
from src.ssi_api.connections import V3_DATA_ROUTES, v3_api_base, v3_stream_url

EXPECTED_BOARD = {"VN30": "HOSE"}  # scope: VN30 only
EXPECTED_MEMBERS = {"VN30": 30}
OTP_PATTERN = re.compile(r"\d{4,8}")
SYMBOL = re.compile(r"[A-Z0-9][A-Z0-9._-]{0,31}")
MAX_PAGES = 20
SUMMARY_MAP = {"open": "openPrice", "high": "highPrice", "low": "lowPrice", "close": "closePrice",
    "average": "averagePrice", "priceChange": "priceChange", "priceChangePercentage": "priceChangePercent",
    "totalMatch": "totalTradingVolume", "totalMatchValue": "totalTradingValue",
    "totalForeignBuy": "foreignBuyVolume", "totalForeignBuyValue": "foreignBuyValue",
    "totalForeignSell": "foreignSellVolume", "totalForeignSellValue": "foreignSellValue",
    "remainForeignRoom": "foreignRemain", "totalForeignRoom": "foreignRoom",
    "totalBuy": "totalBuy", "totalSell": "totalSell", "totalTradeBuy": "totalTradeBuy",
    "totalTradeSell": "totalTradeSell", "totalDeal": "ptTotalTradedVolume", "totalDealValue": "ptTotalTradedValue",
    "refPrice": "refPrice", "ceiling": "ceilingPrice", "floor": "floorPrice"}


class MemberListError(NeoError):
    """SSI answered, but not with the composition of the index (seen live 09/11/2026 at 15:49:
    ``securitiesByBoard?index=VN30`` returned one row, the index itself; at 14:58 it returned 30)."""


def resolve_members(client, groups=("VN30",), database=None):
    """Composition from SSI. If its answer is unusable, the last complete stored session, with a warning."""
    try:
        return client.universe(groups), None
    except MemberListError as error:
        members, warnings = [], []
        for group in groups:
            symbols, day = known_members(database or default_daily_path(), group, EXPECTED_MEMBERS[group])
            if not symbols:
                raise
            members += [{"symbol": s, "index_group": group, "marketCode": EXPECTED_BOARD[group]} for s in symbols]
            warnings.append(f"{error} Dùng tạm thành phần {group} của phiên {day}; cần kiểm tra lại.")
        return members, " ".join(warnings)


def _sdk():
    try:
        import ssi_sdk
        from ssi_sdk import exceptions
    except ImportError:
        raise NeoError("Chưa cài ssi-sdk. Chạy lại CAI_THU_VIEN.ps1 hoặc pip install ssi-sdk==3.3.2.") from None
    return ssi_sdk, exceptions


def sdk_config(settings):
    ssi_sdk, _ = _sdk()
    return ssi_sdk.Config(client_id=settings.client_id, api_url=v3_api_base(settings.rest_base),
        streaming_url=v3_stream_url(settings.stream_base), api_key=settings.api_key, api_secret=settings.api_secret,
        log_level="WARNING", auto_reconnect=False, rate_limit_per_second=2, max_retries=2, timeout_ms=20_000)


def parse_day(value):
    if isinstance(value, str):
        text = value.strip()[:19]
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y%m%d"):
            try:
                return datetime.strptime(text[:len(datetime(2000, 1, 1).strftime(fmt))], fmt).date()
            except ValueError:
                continue
    raise ValueError("Ngày giao dịch V3 không đọc được.")


def _number(value, field, issues):
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        issues.append(field)
        return None
    try:
        result = float(value)
    except (ValueError, OverflowError):
        issues.append(field)
        return None
    if result != result or result in (float("inf"), float("-inf")):
        issues.append(field)
        return None
    return result


def canonical_summary(row, index_group):
    """Daily summary row -> internal names; absent stays None (the SDK would write 0)."""
    if not isinstance(row, dict):
        raise NeoError("Bản ghi securitiesSummary sai kiểu.")
    symbol = row.get("symbol")
    if not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol.strip().upper()):
        raise NeoError("Bản ghi securitiesSummary thiếu mã hợp lệ.")
    issues = []
    result = {"symbol": symbol.strip().upper(), "index_group": index_group,
              "tradingDate": parse_day(row.get("tradingDate")).isoformat()}
    for key, target in SUMMARY_MAP.items():
        result[target] = _number(row.get(key), target, issues) if key in row else None
    result["invalid_fields"] = ";".join(issues)
    result["present_fields"] = ";".join(sorted(k for k in SUMMARY_MAP if k in row))
    return result


class V3Client:
    """Login (optional OTP) and allow-listed GETs. Never trading, account or order routes."""

    def __init__(self, settings, *, auth_factory=None):
        settings.validate_v3()
        self.settings = settings
        self.config = None
        if auth_factory is None:
            ssi_sdk, _ = _sdk()
            self.config = sdk_config(settings)
            auth_factory = ssi_sdk.Auth
        else:
            self.config = getattr(auth_factory, "config", None)
        self.auth = auth_factory(self.config) if self.config is not None else auth_factory()
        self.login_mode = None

    # -- login -----------------------------------------------------------------
    def login(self, otp_mode=None, read_otp=None, notify=print):
        """``none``: token without OTP (REST data). ``prompt``: SMS/email OTP. ``smart``: app approval."""
        mode = otp_mode or self.settings.otp_mode
        try:
            if mode == "none":
                self.auth.authenticate()
            elif mode == "prompt":
                if read_otp is None:
                    raise NeoError("Chế độ OTP prompt cần nhập OTP trên cửa sổ dòng lệnh.")
                self.auth.request_otp()
                notify("Đã yêu cầu SSI gửi OTP. Nhập mã OTP (không hiển thị trên màn hình).")
                code = (read_otp() or "").strip()
                if not OTP_PATTERN.fullmatch(code):
                    raise NeoError("OTP phải gồm 4–8 chữ số.")
                self.auth.authenticate(otp=code)
            elif mode == "smart":
                response = self.auth.token_manager.request_otp_typed()
                transaction = getattr(response, "transaction_id", None)
                if not transaction:
                    raise NeoError("Tài khoản không trả Smart OTP; dùng SSI_OTP_MODE=prompt.")
                notify("Hãy xác nhận yêu cầu đăng nhập trên ứng dụng SSI Smart OTP.")
                self.auth.ensure_authenticated(transaction_id=transaction)
            else:
                raise NeoError("SSI_OTP_MODE phải là none, prompt hoặc smart.")
        except NeoError:
            raise
        except Exception as error:
            raise self._translate(error, "đăng nhập") from None
        self.login_mode = mode
        return mode

    def token_provider(self, force_refresh):
        tm = self.auth.token_manager
        if force_refresh and tm.has_refresh_token:
            tm.refresh()
        return tm.ensure_authenticated()

    def token_expiry(self):
        token = self.auth.token_manager.token
        return getattr(token, "effective_expires_at", 0) if token is not None else 0

    def close(self):
        closer = getattr(self.auth, "close", None)
        if callable(closer):
            closer()

    # -- REST --------------------------------------------------------------------
    def _translate(self, error, action):
        _, exceptions = _sdk()
        if isinstance(error, exceptions.ReauthenticationRequired):
            return AuthError(f"SSI yêu cầu đăng nhập lại bằng OTP mới khi {action}.")
        if isinstance(error, exceptions.AuthenticationError):
            return AuthError(f"SSI từ chối xác thực khi {action}. Kiểm tra API Key/Secret, quyền dữ liệu và OTP.")
        if isinstance(error, exceptions.RateLimitError):
            return NeoError(f"SSI trả HTTP 429 khi {action}; đã dừng, không gửi dồn yêu cầu.")
        if isinstance(error, exceptions.ValidationError):
            return NeoError(f"Tham số {action} không hợp lệ theo SDK.")
        if isinstance(error, exceptions.SSIError):
            code = getattr(error, "status_code", None)
            return NeoError(f"SSI báo lỗi khi {action}" + (f" (HTTP {code})." if code else "."))
        return NeoError(f"Không nhận được phản hồi SSI khi {action}.")

    def get(self, route, params=None):
        if route not in V3_DATA_ROUTES:
            raise NeoError("Chỉ cho phép các route dữ liệu thị trường V3 đã khai báo.")
        if self.login_mode is None:
            raise AuthError("Chưa đăng nhập SSI V3.")
        try:
            return self.auth.rest_client.get("/api/v3/" + V3_DATA_ROUTES[route], params=params or {})
        except Exception as error:
            raise self._translate(error, route) from None

    def index_members(self, index):
        if index not in EXPECTED_BOARD:
            raise NeoError("Nhóm ngoài phạm vi VN30.")
        body = self.get("securitiesByBoard", {"index": index})
        if isinstance(body, dict) and str(body.get("code")) == "204":
            body = []
        if isinstance(body, dict) and isinstance(body.get("data"), list):
            body = body["data"]
        if not isinstance(body, list) or any(not isinstance(row, dict) for row in body):
            raise NeoError("securitiesByBoard trả sai cấu trúc; cần đối chiếu mẫu thật.")
        members, seen = [], set()
        expected = EXPECTED_BOARD[index]
        for row in body:
            symbol = str(row.get("symbol") or "").strip().upper()
            if symbol == index:
                raise MemberListError(f"SSI trả chính chỉ số {index} thay vì danh sách thành phần.")
            if not SYMBOL.fullmatch(symbol) or symbol in seen:
                raise NeoError("Danh sách thành phần thiếu hoặc trùng mã.")
            board = str(row.get("board") or "").strip().upper()
            if board != expected:
                raise NeoError(f"Mã {symbol} không thuộc sàn {expected} của {index}; không tự gán sàn.")
            row_index = row.get("index")
            if row_index not in (None, "") and str(row_index).strip().upper() != index:
                raise NeoError("SSI trả thành phần của nhóm khác yêu cầu.")
            seen.add(symbol)
            members.append({"symbol": symbol, "index_group": index, "marketCode": expected})
        if len(members) != EXPECTED_MEMBERS[index]:
            raise MemberListError(f"SSI trả {len(members)} mã cho {index}, cần {EXPECTED_MEMBERS[index]} mã.")
        return members

    def universe(self, groups=("VN30",)):
        members = [m for group in groups for m in self.index_members(group)]
        if len({m["symbol"] for m in members}) != len(members):
            raise NeoError("Danh sách thành phần có mã trùng; cần kiểm tra dữ liệu thành phần.")
        return members

    def summaries(self, index, from_day, to_day):
        """Daily summary rows of the INDEX itself (observed 07/11/2026: ``index=VN30`` returns the
        index level, one row per day, not its members). Members come from ``member_summaries``."""
        if index not in EXPECTED_BOARD:
            raise NeoError("Nhóm ngoài phạm vi VN30.")
        return self._summary_pages({"index": index}, index, from_day, to_day)

    def symbol_summaries(self, symbol, group, from_day, to_day):
        """Daily summary rows of one listed stock, labelled with its comparison group."""
        if group not in EXPECTED_BOARD or not SYMBOL.fullmatch(str(symbol)):
            raise NeoError("Mã hoặc nhóm không hợp lệ cho securitiesSummary.")
        rows = self._summary_pages({"symbol": symbol}, group, from_day, to_day)
        if any(r["symbol"] != symbol for r in rows):
            raise NeoError("securitiesSummary trả mã khác mã được hỏi.")
        return rows

    def member_summaries(self, members, from_day, to_day):
        """One request per member (the SDK's rate limiter spaces them); stops on the first error."""
        return [row for m in members for row in self.symbol_summaries(m["symbol"], m["index_group"], from_day, to_day)]

    def _summary_pages(self, selector, group, from_day, to_day):
        if not isinstance(from_day, date) or not isinstance(to_day, date) or from_day > to_day:
            raise NeoError("Khoảng ngày securitiesSummary không hợp lệ.")
        rows, page, pages = [], 1, 1
        while page <= pages:
            body = self.get("securitiesSummary", {**selector, "from": from_day.strftime("%Y/%m/%d"),
                "to": to_day.strftime("%Y/%m/%d"), "pageIndex": page, "pageSize": 1000})
            if isinstance(body, dict) and str(body.get("code")) == "204":
                break
            data = body.get("data") if isinstance(body, dict) else None
            if not isinstance(data, list):
                raise NeoError("securitiesSummary trả sai cấu trúc; cần đối chiếu mẫu thật.")
            rows.extend(canonical_summary(row, group) for row in data)
            count = body.get("pagesCount", body.get("pageCount", 1))
            pages = count if isinstance(count, int) and not isinstance(count, bool) and count >= 1 else 1
            if pages > MAX_PAGES:
                raise NeoError("securitiesSummary có quá nhiều trang; thu hẹp khoảng ngày.")
            if not data:
                break
            page += 1
        keys = [(r["symbol"], r["tradingDate"]) for r in rows]
        if len(set(keys)) != len(keys):
            raise NeoError("securitiesSummary trả trùng mã trong cùng ngày.")
        return rows
