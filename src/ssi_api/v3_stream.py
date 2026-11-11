"""FastConnect V3 stream adapter for the transport-independent collector.

The SDK ``WebSocketClient`` runs with ``auto_reconnect=False``: a drop is surfaced to
``collect_stream`` as ``StreamDisconnected`` so that every reconnect starts a new
connection epoch with a fresh bootstrap. Frames are handed over raw (topic + data).
"""
import queue
import threading

from src.data.store import now
from src.neo_api.rest import AuthError
from src.ssi_api.stream_collector import Frame, StreamAuthFailed, StreamDisconnected, validate_members, v3_subscription_plan
from src.ssi_api.v3_client import MemberListError, resolve_members

QUEUE_LIMIT = 50_000
_DROP, _AUTH, _DENIED = "disconnected", "auth_failed", "subscription_denied"


def default_ws_factory(client):
    from ssi_sdk.transport.websocket_client import WebSocketClient
    return WebSocketClient(client.config, token_provider=client.token_provider,
                           expiry_provider=client.token_expiry, auto_reconnect=False)


class V3Stream:
    def __init__(self, client, ws_factory=None, clock=now, limit=QUEUE_LIMIT):
        self.client = client
        self.ws_factory = ws_factory or default_ws_factory
        self.clock = clock
        self.queue = queue.Queue(maxsize=limit)
        self.ws = None
        self.acks = {"ok": 0, "error": 0}
        self.overflow = False
        self._lock = threading.Lock()

    def _signal(self, kind):
        try:
            self.queue.put_nowait((kind, None))
        except queue.Full:
            self.overflow = True

    def _on_data(self, message):
        if not isinstance(message, dict):
            return
        if "topic" not in message:
            # Subscribe/unsubscribe acknowledgement on the DATA channel.
            status = str(message.get("status", "")).lower()
            with self._lock:
                self.acks["error" if status == "error" else "ok"] += 1
            if status == "error":
                self._signal(_DENIED)
            return
        try:
            self.queue.put_nowait(("frame", Frame(message, self.clock())))
        except queue.Full:
            # Never silently thin the record: force a reconnect and a new baseline.
            self.overflow = True

    def _on_error(self, message):
        self._signal(_AUTH if str(message.get("code", "")).startswith("401") else _DROP)

    def _on_state(self, event):
        state = getattr(event, "state", "")
        if state == "failed":
            error = getattr(event, "error", None)
            name = type(error).__name__ if error is not None else ""
            self._signal(_AUTH if "Authentication" in name or "Reauthentication" in name else _DROP)
        elif state == "disconnected":
            self._signal(_DROP)

    def connect(self):
        self.ws = self.ws_factory(self.client)
        self.ws.on("DATA", self._on_data)
        self.ws.on("@error", self._on_error)
        self.ws.on_state = self._on_state
        try:
            self.ws.connect()
        except Exception as error:
            name = type(error).__name__
            if "Authentication" in name or "Reauthentication" in name:
                raise StreamAuthFailed("SSI từ chối mở stream; có thể cần đăng nhập bằng OTP.") from None
            raise StreamDisconnected("connect_failed") from None

    def subscribe(self, topics):
        topics = [t for t in topics if isinstance(t, str) and t]
        if not topics:
            raise ValueError("Danh sách topic V3 rỗng.")
        try:
            self.ws.send({"method": "subscribe", "channel": "DATA", "topics": topics})
        except Exception:
            raise StreamDisconnected("subscribe_failed") from None

    def receive(self, timeout):
        if self.overflow:
            raise StreamDisconnected("queue_overflow")
        try:
            kind, item = self.queue.get(timeout=max(0, timeout))
        except queue.Empty:
            return None
        if kind == "frame":
            return item
        if kind in {_AUTH, _DENIED}:
            raise StreamAuthFailed("SSI từ chối xác thực hoặc từ chối đăng ký topic (quyền dữ liệu).")
        raise StreamDisconnected(kind)

    def close(self):
        if self.ws is not None:
            try:
                self.ws.disconnect()
            finally:
                self.ws = None


class V3Factory:
    """Bootstraps the VN30 universe through REST, then opens one V3 stream."""
    source = "ssi"
    profile = "fastconnect_v3"

    def __init__(self, client, groups=("VN30",), subscribe_mode="index", ws_factory=None):
        if subscribe_mode not in {"index", "symbols"}:
            raise ValueError("subscribe_mode phải là index hoặc symbols.")
        self.client, self.groups, self.subscribe_mode, self.ws_factory = client, tuple(groups), subscribe_mode, ws_factory
        self.last_stream = None
        self.members = None

    def bootstrap(self):
        """A reconnect keeps the composition it already has if SSI's list turns unusable mid-run."""
        try:
            if self.members is None:
                self.members = resolve_members(self.client, self.groups)[0]
            else:
                try:
                    self.members = self.client.universe(self.groups)
                except MemberListError:
                    pass
        except AuthError:
            raise StreamAuthFailed("SSI từ chối xác thực khi lấy thành phần VN30.") from None
        return self.members

    def create(self):
        self.last_stream = V3Stream(self.client, self.ws_factory)
        return self.last_stream

    def topics(self, members):
        if self.subscribe_mode == "index":
            return v3_subscription_plan(members)
        symbols = sorted(validate_members(members))
        return tuple(f"{kind}.{symbol}" for symbol in symbols for kind in ("trade", "quote", "room")) + ("market.flag",)
