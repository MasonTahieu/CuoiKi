"""Market-only connection settings. No network during configuration loading."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values
from src.config import PROJECT_ROOT, ConfigurationError


@dataclass(frozen=True)
class NeoSettings:
    token: str = field(default="", repr=False)
    device: str = field(default="", repr=False)
    device_type: str = "chrome"
    ws_url: str = ""
    wire_format: str = "bare"
    update_mode: str = "snapshot"
    semantics_verified: bool = False
    database: Path = PROJECT_ROOT / "runtime" / "neo.sqlite"

    def validate(self, websocket=False):
        if not self.token or not self.device or not self.device_type:
            raise ConfigurationError("Cần NEO_ACCESS_TOKEN, NEO_DEVICE_ID và NEO_DEVICE_TYPE trong .env.")
        if any(c in self.token + self.device + self.device_type for c in "\r\n"):
            raise ConfigurationError("Cấu hình xác thực chứa ký tự xuống dòng không hợp lệ.")
        if self.token.lower().startswith("bearer "):
            raise ConfigurationError("NEO_ACCESS_TOKEN chỉ chứa token, không kèm tiền tố Bearer.")
        if websocket:
            url = urlsplit(self.ws_url)
            if (url.scheme != "wss" or url.hostname != "neoapi.vpbanks.com.vn"
                    or url.path != "/stock-stream/broker" or url.port not in (None, 443)
                    or url.username or url.password or url.query or url.fragment):
                raise ConfigurationError("Cần URL WSS thị trường chính thức được VPBS xác nhận; không dùng WS hoặc trading-stream.")


def load_neo_settings(env_file=None):
    values = dotenv_values(env_file or PROJECT_ROOT / ".env", interpolate=False)
    def get(key, default=""):
        return str(os.environ.get(key, values.get(key) or default)).strip()
    wire = get("NEO_WS_FORMAT", "bare")
    mode = get("NEO_UPDATE_MODE", "snapshot")
    verified = get("NEO_SEMANTICS_VERIFIED", "false").lower()
    if wire not in {"bare", "channel_data"} or mode not in {"snapshot", "patch"}:
        raise ConfigurationError("NEO_WS_FORMAT=bare/channel_data; NEO_UPDATE_MODE=snapshot/patch.")
    if verified not in {"true", "false"}:
        raise ConfigurationError("NEO_SEMANTICS_VERIFIED phải là true hoặc false.")
    path = Path(get("NEO_DATABASE", "runtime/neo.sqlite"))
    return NeoSettings(token=get("NEO_ACCESS_TOKEN"), device=get("NEO_DEVICE_ID"),
        device_type=get("NEO_DEVICE_TYPE", "chrome"), ws_url=get("NEO_WS_URL"),
        wire_format=wire, update_mode=mode, semantics_verified=verified == "true",
        database=path if path.is_absolute() else PROJECT_ROOT / path)
