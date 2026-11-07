"""Đọc fixture giả lập cục bộ; không gọi mạng hay tự tạo dữ liệu thật."""

from pathlib import Path

import numpy as np
import pandas as pd

from src.config import DEMO_PATH

SOURCE = "synthetic"
DEMO_LABEL = "DỮ LIỆU GIẢ LẬP — chỉ kiểm tra khung dự án"
REQUIRED = {
    "source", "observed_at", "symbol", "price_vnd", "volume_shares",
    "turnover_vnd", "foreign_buy_vnd", "foreign_sell_vnd",
}
NUMERIC = [
    "price_vnd", "volume_shares", "turnover_vnd",
    "foreign_buy_vnd", "foreign_sell_vnd",
]


class DemoDataError(ValueError):
    """Fixture không đáp ứng hợp đồng dữ liệu P2."""


def load_demo(path: Path = DEMO_PATH) -> pd.DataFrame:
    try:
        frame = pd.read_csv(path, dtype={"symbol": "str", "source": "str"})
    except (OSError, ValueError):
        raise DemoDataError("Không đọc được tệp dữ liệu giả lập. Kiểm tra data_sample/.") from None
    if not REQUIRED.issubset(frame.columns) or frame.empty:
        raise DemoDataError("Dữ liệu giả lập trống hoặc thiếu cột bắt buộc.")
    if not frame["source"].eq(SOURCE).all():
        raise DemoDataError("Mọi dòng mẫu phải có source=synthetic; không trộn dữ liệu thật.")
    if not frame["symbol"].str.fullmatch(r"DEMO\d{2}", na=False).all():
        raise DemoDataError("Mẫu P2 phải dùng mã DEMOxx để tránh nhầm cổ phiếu thật.")
    if not frame["observed_at"].astype(str).str.endswith("+07:00").all():
        raise DemoDataError("Mẫu cần thời gian có offset +07:00.")
    try:
        frame["observed_at"] = pd.to_datetime(frame["observed_at"], utc=True).dt.tz_convert(
            "Asia/Ho_Chi_Minh"
        )
        for column in NUMERIC:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
    except (ValueError, TypeError):
        raise DemoDataError("Mẫu có thời gian hoặc số liệu không hợp lệ.") from None
    if frame["observed_at"].isna().any():
        raise DemoDataError("Mẫu có thời gian bị thiếu.")
    if not np.isfinite(frame[NUMERIC].to_numpy(dtype=float)).all():
        raise DemoDataError("Mẫu có số thiếu hoặc không hữu hạn.")
    if (frame[NUMERIC] < 0).any().any() or (frame["price_vnd"] <= 0).any():
        raise DemoDataError("Mẫu có giá không dương hoặc khối lượng/giá trị âm.")
    if frame.duplicated(["symbol", "observed_at"]).any():
        raise DemoDataError("Mẫu có mã và thời gian trùng nhau.")
    return frame.sort_values(["observed_at", "symbol"]).reset_index(drop=True)


def latest_snapshot(frame: pd.DataFrame) -> pd.DataFrame:
    """Chỉ lấy mốc mẫu cuối, không gộp mốc cũ vào cùng một ảnh chụp."""
    return frame.loc[frame["observed_at"].eq(frame["observed_at"].max())].copy()

