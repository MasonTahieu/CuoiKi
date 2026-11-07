"""Public connection contracts, verified against SSI docs and official FCData client.

No credentials are read here. These are documented addresses, not a live health check.
"""
from urllib.parse import urlsplit
from src.config import ConfigurationError

FC_REST = "https://fc-data.ssi.com.vn/api/v2/Market/"
FC_STREAM = "https://fc-datahub.ssi.com.vn/v2.0/signalr"
V3_API = "https://api.ssi.com.vn"
V3_REST = V3_API + "/api/v3/"
V3_STREAM = "wss://stream.ssi.com.vn/ws/v3"
V3_SDK = "ssi-sdk==3.3.2"
V3_DATA_ROUTES = {"securitiesByBoard":"data/securitiesByBoard","securitiesSummary":"data/securitiesSummary",
    "masterData":"data/masterdata","indexList":"data/indexList","indexSummary":"data/indexSummary","ohlc":"data/ohlc"}
# Stream topics used by this project (read-only market data). ``@*`` fans a basket index out to its members.
V3_GROUP_TOPICS = ("trade","quote","room")
V3_BOARD_TOPICS = ("market.flag",)
FC_METHODS = ("Securities", "SecuritiesDetails", "IndexList", "IndexComponents", "DailyOhlc", "IntradayOhlc", "DailyIndex", "DailyStockPrice")


def connection_plan(profile="unselected"):
    plans = {
        "fcdata_v2": {
            "rest_base":FC_REST, "auth_url":FC_REST+"AccessToken",
            "market_routes":{name:FC_REST+name for name in FC_METHODS},
            "stream_url":FC_STREAM,"stream_transport":"signalr",
            "sdk_stream_base":"https://fc-datahub.ssi.com.vn/",
            "hub":"FcMarketDataV2Hub", "receive_method":"Broadcast", "subscribe_method":"SwitchChannels",
            "channel_templates":["F:{symbols}","X:{symbols}","X-Quote:{symbols}","X-Trade:{symbols}","R:{symbols}","B:{symbols}"],
            "symbol_separator":"-", "rest_implemented":True,"stream_implemented":False,
            "references":["https://github.com/SSI-Securities-Corporation/python-fcdata/blob/master/ssi_fc_data/model/api.py",
                          "https://guide.ssi.com.vn/ssi-products/fastconnect-data/streaming-data"],
        },
        "fastconnect_v3": {
            "rest_base":V3_REST, "auth_url":V3_REST+"auth/token", "refresh_url":V3_REST+"auth/refresh",
            "otp_url":V3_REST+"auth/requestOtp",
            "market_routes":{name:V3_REST+path for name,path in V3_DATA_ROUTES.items()},
            "stream_url":V3_STREAM,"stream_transport":"websocket","sdk":V3_SDK,
            "subscribe_frame":{"method":"subscribe","channel":"DATA","topics":["trade.VN30@*","quote.VN30@*","room.VN30@*"]},
            "topics":[f"{kind}.{{VN30|HNX30}}@*" for kind in V3_GROUP_TOPICS]+list(V3_BOARD_TOPICS),
            "auth_note":"REST dữ liệu dùng token không OTP; tài liệu SDK yêu cầu đăng nhập có OTP trước khi mở stream. Cần xác nhận với tài khoản thật.",
            "session_note":"Server giữ một phiên cho mỗi apiKey: REST và stream phải dùng chung một đăng nhập trong một tiến trình.",
            "rest_implemented":True,"stream_implemented":True,
            "references":["https://developers.ssi.com.vn/docs/getting-started/overview",
                          "https://developers.ssi.com.vn/docs/getting-started/registration",
                          "https://pypi.org/project/ssi-sdk/3.3.2/"],
        },
    }
    if profile not in (*plans,"unselected"):
        raise ConfigurationError("Phiên bản SSI không được hỗ trợ.")
    return {"network_called":False,"live_verified":False,"selected_profile":profile,
            "profiles":plans if profile=="unselected" else {profile:plans[profile]}}


def fcdata_rest_base(override=""):
    candidate = override or FC_REST
    try:
        parsed = urlsplit(candidate)
        valid = (parsed.scheme=="https" and parsed.hostname=="fc-data.ssi.com.vn"
            and parsed.path.rstrip("/")=="/api/v2/Market" and parsed.port in (None,443)
            and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment)
    except ValueError:
        valid=False
    if not valid:
        raise ConfigurationError("SSI_REST_BASE phải là HTTPS FCData v2 đúng host/path chính thức; không thử URL khác tự động.")
    return candidate.rstrip("/")+"/"


def _check_url(candidate, scheme, host, path, label):
    try:
        parsed = urlsplit(candidate)
        valid = (parsed.scheme==scheme and parsed.hostname==host and parsed.path.rstrip("/")==path
            and parsed.port in (None,443) and not parsed.username and not parsed.password
            and not parsed.query and not parsed.fragment)
    except ValueError:
        valid=False
    if not valid:
        raise ConfigurationError(f"{label} phải đúng địa chỉ V3 chính thức; không thử URL khác tự động.")


def v3_api_base(override=""):
    """SDK api_url (host only). Accepts the documented host with or without /api/v3."""
    candidate=(override or V3_API).rstrip("/")
    if candidate.endswith("/api/v3"):
        candidate=candidate[:-len("/api/v3")]
    _check_url(candidate,"https","api.ssi.com.vn","","SSI_REST_BASE")
    return candidate


def v3_stream_url(override=""):
    candidate=(override or V3_STREAM).rstrip("/")
    _check_url(candidate,"wss","stream.ssi.com.vn","/ws/v3","SSI_STREAM_BASE")
    return candidate
