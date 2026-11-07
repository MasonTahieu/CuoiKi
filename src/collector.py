"""Independent bounded market collector, deliberately not started by the UI."""
import json
import time
import uuid
import websocket

from src.data.store import EventStore, now
from src.neo_api.rest import RestClient, NeoError, AuthError
from src.neo_api.stream import auth_message, subscriptions, decode_message


def bootstrap(client, store, run):
    members = client.vn30()
    at = now()
    store.append("neo", run, at, "universe", {"index":"VN30", "members":members})
    for member in members:
        store.append("neo", run, at, "stockInfo", member)
    states = client.get("market_status", marketCode="HOSE")["data"]
    if not isinstance(states, list) or not states or not all(isinstance(s, dict) for s in states):
        raise NeoError("marketStatus không có cấu trúc danh sách như tài liệu.")
    for state in states:
        store.append("neo", run, now(), "marketSession", state)
    return [r["symbol"] for r in members]


def collect(settings, seconds=300, transport="ws"):
    if not 1 <= seconds <= 28800 or transport not in {"ws", "rest"}:
        raise ValueError("Thời lượng cần từ 1 đến 28800 giây; transport=ws/rest.")
    settings.validate(websocket=transport == "ws")
    client, store = RestClient(settings), EventStore(settings.database)
    run = "neo-" + uuid.uuid4().hex
    deadline = time.monotonic() + seconds
    count = 0
    def status(state):
        store.append("neo", run, now(), "connection", {"state":state,
            "update_mode":settings.update_mode, "wire_format":settings.wire_format,
            "semantics_verified":settings.semantics_verified})
    try:
        # REST mode is a one-shot diagnostic, not a substitute for WebSocket evidence.
        if transport == "rest":
            status("connecting")
            symbols = bootstrap(client, store, run)
            status("snapshot_complete")
            return {"source":"neo", "run":run, "symbols":len(symbols), "transport":"rest"}
        for attempt in range(4):
            sock = None
            if time.monotonic() >= deadline:
                break
            try:
                status("connecting")
                # Refresh all baselines on every reconnect: never merge across a gap.
                symbols = bootstrap(client, store, run)
                sock = websocket.create_connection(settings.ws_url, timeout=15,
                    redirect_limit=0, header={"x-device":settings.device, "x-devicetype":settings.device_type})
                sock.send(auth_message(settings.token))
                channel, _ = decode_message(sock.recv(), settings.wire_format)
                if channel != "auth":
                    raise AuthError("Chưa có xác nhận auth thành công; không gửi đăng ký.")
                for subscription in subscriptions(symbols):
                    sock.send(json.dumps(subscription))
                status("connected")
                idle = 0
                while time.monotonic() < deadline:
                    sock.settimeout(max(0.1, min(15, deadline-time.monotonic())))
                    try:
                        raw = sock.recv()
                    except websocket.WebSocketTimeoutException:
                        idle += 1
                        if idle >= 3:
                            raise NeoError("Không nhận dữ liệu sau ba khoảng chờ.")
                        sock.ping()
                        continue
                    if not raw:
                        raise NeoError("Luồng đã đóng.")
                    idle = 0
                    try:
                        channel, payload = decode_message(raw, settings.wire_format)
                    except AuthError:
                        raise
                    except NeoError:
                        status("unrecognized_message")  # no arbitrary body persisted/logged
                        continue
                    if channel == "auth":
                        continue
                    if channel == "stockInfo" and payload.get("symbol") not in symbols:
                        continue
                    store.append("neo", run, now(), channel, payload)
                    count += 1
                status("stopped")
                return {"source":"neo", "run":run, "messages":count, "transport":"ws"}
            except AuthError:
                status("auth_failed")
                raise
            except (NeoError, OSError, websocket.WebSocketException):
                status("disconnected")
                if attempt == 3:
                    raise NeoError("Đã hết 3 lần kết nối lại. Xem nhật ký trạng thái, quyền và URL WSS.") from None
                time.sleep(min(2**attempt, max(0, deadline-time.monotonic())))
            finally:
                if sock is not None:
                    sock.close()
        raise NeoError("Hết thời lượng trước khi hoàn tất luồng nhận dữ liệu.")
    finally:
        client.close()
        store.close()
