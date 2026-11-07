"""Cấu hình giao diện. Cấu hình NEO được tách tại neo_api/settings.py."""

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "data_sample" / "synthetic_quotes.csv"


class ConfigurationError(ValueError):
    """Lỗi cấu hình có thông báo an toàn để hiển thị."""


@dataclass(frozen=True)
class Settings:
    mode: str = "demo"
    timezone: str = "Asia/Ho_Chi_Minh"
    provider: str = "ssi"


def load_settings(env_file: Path | None = None) -> Settings:
    # Đường dẫn cố định theo dự án, không tự tìm .env ở thư mục cha.
    values = dotenv_values(env_file or PROJECT_ROOT / ".env", interpolate=False)
    mode = os.environ.get("APP_MODE", values.get("APP_MODE") or "demo").strip()
    timezone = os.environ.get(
        "APP_TIMEZONE", values.get("APP_TIMEZONE") or "Asia/Ho_Chi_Minh"
    ).strip()
    provider = os.environ.get("DATA_PROVIDER", values.get("DATA_PROVIDER") or "ssi").strip()
    if provider not in {"ssi", "neo"}:
        raise ConfigurationError("DATA_PROVIDER chỉ hỗ trợ ssi hoặc neo.")
    if mode not in {"demo", "live", "replay"}:
        raise ConfigurationError(
            "APP_MODE chỉ hỗ trợ demo, replay hoặc live."
        )
    if timezone != "Asia/Ho_Chi_Minh":
        raise ConfigurationError("Sử dụng APP_TIMEZONE=Asia/Ho_Chi_Minh (UTC+7).")
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        raise ConfigurationError("Thiếu dữ liệu múi giờ. Cài các gói trong requirements.txt.") from None
    return Settings(mode=mode, timezone=timezone, provider=provider)

