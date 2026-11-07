"""Read-only official market endpoints; bounded retry and strict pagination."""
import time
import requests

BASE_URL = "https://neoapi.vpbanks.com.vn/neo-api"
ENDPOINTS = {
    "index_list": "/market/indexList", "index_intraday": "/market/intradayMarketIndex",
    "index_detail": "/market/marketIndexDetail", "market_status": "/market/marketStatus",
    "stock_list": "/stock/stockList", "stock_detail": "/stock/stockDetail",
    "vn30": "/stock/stockDetailByIndex", "odd_lot": "/stock/oddLotStockDetail",
    "futures": "/stock/fuStockDetail",
}


class NeoError(RuntimeError):
    """Safe message only: never include body, token, headers or request repr."""


class AuthError(NeoError):
    pass


class RestClient:
    def __init__(self, settings, session=None, sleep=time.sleep, clock=time.monotonic):
        settings.validate()
        self.settings = settings
        self.session = session or requests.Session()
        self.sleep, self.clock, self.last = sleep, clock, None

    def close(self):
        self.session.close()

    def get(self, endpoint, **params):
        if endpoint not in ENDPOINTS:
            raise NeoError("Chỉ cho phép các endpoint đọc dữ liệu thị trường đã khai báo.")
        headers = {"Authorization": "Bearer " + self.settings.token,
                   "x-device": self.settings.device, "x-devicetype": self.settings.device_type}
        for attempt in range(3):
            if self.last is not None:
                self.sleep(max(0, 0.3 - (self.clock() - self.last)))
            self.last = self.clock()  # <= 3.34 RPS for this single collector process
            try:
                response = self.session.get(BASE_URL + ENDPOINTS[endpoint], params=params,
                    headers=headers, timeout=(5, 15), allow_redirects=False)
            except requests.RequestException:
                if attempt == 2:
                    raise NeoError("Không nhận được phản hồi REST sau 3 lần thử.") from None
                self.sleep(2 ** attempt)
                continue
            if response.status_code in (401, 403):
                raise AuthError("NEO từ chối xác thực/quyền/IP. Kiểm tra hoặc thay token; không tự đăng nhập lại.")
            if response.status_code == 429 or 500 <= response.status_code < 600:
                if attempt == 2:
                    raise NeoError("NEO đang giới hạn tần suất hoặc lỗi máy chủ sau 3 lần thử.")
                try:
                    delay = min(60, max(2 ** attempt, float(response.headers.get("Retry-After", 0))))
                except (TypeError, ValueError):
                    delay = 2 ** attempt
                self.sleep(delay)
                continue
            if response.status_code != 200:
                raise NeoError(f"REST trả HTTP {response.status_code}; đã dừng, không theo redirect.")
            try:
                body = response.json()
            except ValueError:
                raise NeoError("Phản hồi REST không phải JSON.") from None
            if not isinstance(body, dict) or body.get("status") != 1 or "data" not in body:
                raise NeoError("NEO báo lỗi nghiệp vụ hoặc cấu trúc phản hồi khác tài liệu; cần đối chiếu P1.")
            return body
        raise NeoError("Không thể hoàn tất REST.")

    def vn30(self):
        rows, seen, total, pages = [], set(), None, None
        for page in range(1, 101):
            body = self.get("vn30", indexCode="VN30", pageNo=page, pageSize=100)
            data = body["data"]
            if not isinstance(data, dict) or not isinstance(data.get("content"), list):
                raise NeoError("Thiếu data.content trong danh sách VN30.")
            count, page_count = data.get("totalElements"), data.get("totalPages")
            if (type(count) is not int or type(page_count) is not int or count < 1
                    or page_count < 1 or page_count > 100):
                raise NeoError("Thông tin phân trang VN30 không hợp lệ.")
            if total is not None and (total != count or pages != page_count):
                raise NeoError("Danh sách VN30 thay đổi giữa các trang; cần lấy lại snapshot.")
            total, pages = count, page_count
            for row in data["content"]:
                symbol = row.get("symbol") if isinstance(row, dict) else None
                if not isinstance(symbol, str) or not symbol or symbol in seen:
                    raise NeoError("Danh sách VN30 thiếu mã hoặc trùng mã giữa các trang.")
                if row.get("marketCode") != "HOSE" or row.get("stockType") != "ST":
                    raise NeoError("VN30 có loại chứng khoán/sàn ngoài phạm vi dự án.")
                seen.add(symbol)
                rows.append(row)
            if page == pages:
                if len(rows) != total:
                    raise NeoError("Số mã VN30 không khớp totalElements; không dùng danh sách thiếu.")
                return rows
        raise NeoError("Vượt giới hạn phân trang.")
