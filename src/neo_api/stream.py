"""Protocol boundary. Only explicitly supported market payloads pass through."""
import json
from src.neo_api.rest import NeoError, AuthError


def auth_message(token):
    return json.dumps({"action": "auth", "data": token})


def subscriptions(symbols):
    return [{"type":"sub", "channel":"stockInfo", "listId":list(symbols)},
            {"type":"sub", "channel":"marketSession", "listId":["HOSE"]}]


def decode_message(raw, wire_format="bare"):
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        raise NeoError("WebSocket gửi nội dung không phải JSON.") from None
    if not isinstance(data, dict):
        raise NeoError("WebSocket gửi cấu trúc chưa hỗ trợ; cần kiểm tra envelope tại P1.")
    if data.get("type") == "auth":
        if data.get("status") != "success":
            raise AuthError("WebSocket từ chối token. Thay token và chạy lại.")
        return "auth", {}  # auth response may contain account identifiers; never persist it
    if wire_format == "channel_data":
        channel, payload = data.get("channel"), data.get("data")
        if channel not in {"stockInfo", "marketSession", "marketInfo", "marketVolume"} or not isinstance(payload, dict):
            raise NeoError("Envelope channel/data không khớp cấu hình.")
        return channel, payload
    if wire_format != "bare":
        raise NeoError("Định dạng WebSocket chưa hỗ trợ.")
    if "symbol" in data:
        return "stockInfo", data
    if "marketCode" in data and "marketStatus" in data and "indexCode" not in data:
        return "marketSession", data
    if "indexCode" in data:
        return ("marketVolume" if "volume" in data else "marketInfo"), data
    raise NeoError("Thông điệp chưa nhận diện; không đoán cấu trúc hoặc đưa vào điểm.")
