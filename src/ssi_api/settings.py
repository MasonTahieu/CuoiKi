import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import dotenv_values
from src.config import PROJECT_ROOT, ConfigurationError

OTP_MODES = {"none", "prompt", "smart"}
SUBSCRIBE_MODES = {"index", "symbols"}


@dataclass(frozen=True)
class SSISettings:
    profile: str = "unselected"
    consumer_id: str = field(default="", repr=False)
    consumer_secret: str = field(default="", repr=False)
    api_key: str = field(default="", repr=False)
    api_secret: str = field(default="", repr=False)
    database: Path = PROJECT_ROOT / "runtime" / "ssi.sqlite"
    update_mode: str = "patch"
    semantics_verified: bool = False
    rest_base: str = ""
    stream_base: str = ""
    client_id: str = field(default="", repr=False)
    otp_mode: str = "prompt"
    subscribe_mode: str = "index"

    def missing(self):
        if self.profile == "fcdata_v2":
            pairs = [("SSI_CONSUMER_ID",self.consumer_id),("SSI_CONSUMER_SECRET",self.consumer_secret)]
        elif self.profile == "fastconnect_v3":
            pairs = [("SSI_API_KEY",self.api_key),("SSI_API_SECRET",self.api_secret)]
        else:
            return ["SSI_API_PROFILE"]
        return [key for key,value in pairs if not value]

    def validate_v2(self):
        if self.profile != "fcdata_v2":
            raise ConfigurationError("Chọn đúng phiên bản SSI được cấp. Bộ REST này dành cho fcdata_v2; V3 dùng src.ssi_api.v3_client.")
        if self.missing():
            raise ConfigurationError("Thiếu cấu hình SSI: " + ", ".join(self.missing()))

    def validate_v3(self):
        if self.profile != "fastconnect_v3":
            raise ConfigurationError("Bộ nối V3 chỉ chạy khi SSI_API_PROFILE=fastconnect_v3.")
        if self.missing():
            raise ConfigurationError("Thiếu cấu hình SSI: " + ", ".join(self.missing()))


def load_ssi_settings(env_file=None):
    values = dotenv_values(env_file or PROJECT_ROOT / ".env",interpolate=False)
    def get(key,default=""):
        return str(os.environ.get(key,values.get(key) or default)).strip()
    profile = get("SSI_API_PROFILE","unselected")
    if profile not in {"unselected","fcdata_v2","fastconnect_v3"}:
        raise ConfigurationError("SSI_API_PROFILE=unselected/fcdata_v2/fastconnect_v3.")
    verified=get("SSI_SEMANTICS_VERIFIED","false").lower()
    if verified not in {"true","false"}:
        raise ConfigurationError("SSI_SEMANTICS_VERIFIED phải là true hoặc false.")
    otp_mode=get("SSI_OTP_MODE","prompt").lower()
    if otp_mode not in OTP_MODES:
        raise ConfigurationError("SSI_OTP_MODE phải là none, prompt hoặc smart.")
    subscribe_mode=get("SSI_V3_SUBSCRIBE","index").lower()
    if subscribe_mode not in SUBSCRIBE_MODES:
        raise ConfigurationError("SSI_V3_SUBSCRIBE phải là index hoặc symbols.")
    path=Path(get("SSI_DATABASE","runtime/ssi.sqlite"))
    return SSISettings(profile,get("SSI_CONSUMER_ID"),get("SSI_CONSUMER_SECRET"),get("SSI_API_KEY"),get("SSI_API_SECRET"),
        path if path.is_absolute() else PROJECT_ROOT/path,semantics_verified=verified=="true",
        rest_base=get("SSI_REST_BASE"),stream_base=get("SSI_STREAM_BASE"),client_id=get("SSI_CLIENT_ID"),
        otp_mode=otp_mode,subscribe_mode=subscribe_mode)
