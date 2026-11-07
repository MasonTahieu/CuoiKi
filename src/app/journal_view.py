"""UI controls and display for SSI replay snapshots."""
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import streamlit as st

from src.data.ssi_journal import SSIJournal
from src.data.ssi_quality import NEEDED
from src.data.store import now, timestamp
from src.ssi_api.collect_sample import scenario
from src.ssi_api.replay import replay
from src.ssi_api.replay_sample import REASONS, save_sample, stale_scenario


CONNECTION_LABELS = {
    "unknown": "Chưa có trạng thái kết nối",
    "connecting": "Đang kết nối",
    "awaiting_bootstrap": "Đang chờ snapshot",
    "connected": "Đã kết nối",
    "disconnected": "Mất kết nối",
    "auth_failed": "Xác thực thất bại",
    "adapter_error": "Lỗi bộ kết nối",
    "stopped": "Đã dừng thu thập",
    "decode_error": "Thông điệp lỗi",
}
WARNINGS = {
    "FOREIGN_VALUE_ESTIMATED": "Giá trị ngoại ước tính",
    "SOURCE_CLOCK_AHEAD_OF_RECEIVE": "Đồng hồ nguồn đi trước giờ nhận",
    "SESSION_FROM_SCHEDULE": "Phiên suy từ lịch giao dịch (chưa nhận cờ phiên)",
    "SYMBOL_STATUS_NOT_PROVIDED": "V3 không gửi trạng thái từng mã",
    "TOTAL_VALUE_DERIVED": "Giá trị khớp = giá bình quân × khối lượng",
}
BOOK_FIELDS = tuple(field for field in NEEDED if field.startswith(("bid", "ask")))


@st.cache_resource
def sample_journal():
    folder = TemporaryDirectory(prefix="ssi-ui-demo-")
    path = Path(folder.name) / "demo.sqlite"
    primary = save_sample(path, *scenario())
    stale = save_sample(path, *stale_scenario(), seconds=65, max_messages=100)
    labels = {primary["run"]: "Mất kết nối và phục hồi", stale["run"]: "Dữ liệu khối ngoại cũ"}
    return folder, path, labels


def read_journal_view(path, mode, sample_labels=None):
    """Return a selected run and replay result. Legacy stores have no SSI runs."""
    with SSIJournal(path) as journal:
        runs = journal.runs()
    if not runs:
        return None
    if mode == "live":
        runs = [run for run in runs if run["source"] == "ssi"]
        if not runs:
            raise ValueError("Chế độ live cần lần thu thập SSI thật trong kho đã chọn.")
        selected = runs[0]
        return selected, replay(path, selected["run"], as_of=now())

    runs_by_id = {run["run"]: run for run in runs}
    options = list(sample_labels) if sample_labels else list(runs_by_id)

    def run_label(run_id):
        if sample_labels:
            return sample_labels[run_id]
        run = runs_by_id[run_id]
        last = timestamp(run["last_received_at"]).strftime("%d/%m %H:%M:%S")
        return f"{last} · {run['source']} · …{run_id[-8:]}"

    with st.sidebar:
        run_id = st.selectbox("Lần thu thập", options, format_func=run_label)
        with SSIJournal(path) as journal:
            points = journal.timeline(run_id)
        by_id = {point["event_id"]: point for point in points}
        if not by_id:
            return runs_by_id[run_id], replay(path, run_id)

        def point_label(event_id):
            point = by_id[event_id]
            at = timestamp(point["received_at"]).strftime("%d/%m %H:%M:%S")
            label = CONNECTION_LABELS.get(point["state"], "Bản ghi trạng thái")
            if point["channel"] != "connection":
                label = "Dữ liệu cổ phiếu" if point["channel"] == "ssiDecoded" else "Danh sách mã"
            return f"{at} · {label} · #{event_id}"

        decoded_ids = [point["event_id"] for point in points if point["channel"] == "ssiDecoded"]
        default = decoded_ids[-1] if sample_labels and decoded_ids else points[-1]["event_id"]
        event_id = st.selectbox("Mốc phát lại (UTC+7)", list(by_id), index=list(by_id).index(default),
                                format_func=point_label, key=f"replay_point_{run_id}")
        st.caption("Tối đa 200 mốc gần nhất trong lần thu thập. Số thứ tự phân biệt các bản ghi cùng giây.")
    return runs_by_id[run_id], replay(path, run_id, through_event_id=event_id)


def reason_text(reason):
    if reason == "SESSION_NOT_LO":
        return "Ngoài phiên LO hoặc chưa rõ phiên"
    return REASONS.get(reason, reason)


def snapshot_frame(report):
    rows = []
    for row in report["rows"]:
        rows.append({
            **row["payload"], "symbol": row["symbol"], "marketCode": row["marketCode"],
            "index_group": row["index_group"], "source": report["source"],
            "run": report["run"], "as_of": report["as_of"], "event_id": report["last_applied_event_id"],
            "session": row.get("trading_session", row["payload"].get("tradingSession")),
            "quality_reason": " · ".join(reason_text(reason) for reason in row["reasons"]),
            "foreign_value_estimated": bool(row["metadata"].get("foreign_value_estimated")),
            "data_warning": " · ".join(WARNINGS.get(warning, warning) for warning in row["warnings"]),
        })
    return pd.DataFrame(rows)


def connection_summary(report, mode):
    state = report["last_recorded_connection_state"]
    label = CONNECTION_LABELS.get(state, state)
    prefix = "Trạng thái ghi gần nhất" if mode == "live" else "Kết nối tại mốc chọn"
    message = f"{prefix} · {label}"
    if report["connection_epoch"] is not None:
        message += f" · Lần kết nối {report['connection_epoch']}"
    if state in {"disconnected", "auth_failed", "adapter_error", "stopped"}:
        st.warning(message)
    else:
        st.info(message)


def _age(row, fields):
    ages = row["source_age_seconds"]
    if any(field not in ages for field in fields):
        return "—"
    return f"{max(ages[field] for field in fields):g}"


def render_quality(report, ranked, group):
    rows = {row["symbol"]: row for row in report["rows"] if row["index_group"] == group}
    coverage = report["group_coverage"][group]
    st.subheader("Chất lượng theo mã")
    st.caption(f"{coverage['data_usable']}/{coverage['members']} mã đạt kiểm tra dữ liệu. "
               "Tuổi hiển thị theo giây, lấy trường lâu nhất trong mỗi cụm.")
    overview = []
    for row in ranked.to_dict("records"):
        quality = rows[row["symbol"]]
        payload = quality["payload"]
        overview.append({
            "Mã": row["symbol"], "Phiên": payload.get("tradingSession") or "—",
            "Trạng thái mã": payload.get("tradingStatus") or "—",
            "Giá và khớp (s)": _age(quality, ("closePrice", "totalTradingValue")),
            "Sổ lệnh (s)": _age(quality, BOOK_FIELDS),
            "Khối ngoại (s)": _age(quality, ("foreignBuyValue", "foreignSellValue")),
            "Cảnh báo": row["data_warning"], "Lý do chưa xếp hạng": row["quality_reason"],
        })
    st.dataframe(pd.DataFrame(overview), hide_index=True, width="stretch")
    policy = report["policy"]
    st.caption(f"Ngưỡng cũ cho trường động là {policy['max_age_seconds']:g} giây. "
               "Dấu — nghĩa là cụm chưa đủ thời gian nguồn. Chênh nguồn–nhận có thể gồm lệch đồng hồ.")
    with st.expander("Xem dấu thời gian từng trường"):
        symbol = st.selectbox("Mã kiểm tra dữ liệu", sorted(rows))
        row = rows[symbol]
        reason = ranked.loc[ranked["symbol"].eq(symbol), "quality_reason"].iloc[0]
        if reason:
            st.info(reason)
        fields = []
        for field in NEEDED:
            marks = []
            for key, label in (("missing_fields", "Thiếu"), ("stale_fields", "Cũ"),
                               ("invalid_fields", "Giá trị sai"), ("time_missing_fields", "Thiếu giờ nguồn/nhận"),
                               ("lagging_fields", "Chênh giờ lớn")):
                if field in row[key]:
                    marks.append(label)
            fields.append({
                "Trường": field, "Giờ nguồn": row["field_updated_at"].get(field),
                "Giờ nhận": row["field_received_at"].get(field), "Tuổi nguồn (s)": row["source_age_seconds"].get(field),
                "Chênh nguồn–nhận (s)": row["recorded_lag_seconds"].get(field),
                "Đánh giá": " · ".join(marks) or "Đạt",
            })
        st.dataframe(pd.DataFrame(fields), hide_index=True, width="stretch")
    if report["gaps"]:
        gaps = [{
            "Từ": gap["start"], "Đến": gap["end"], "Giây": gap["seconds"],
            "Trạng thái": "Đang mở" if gap["open_ended"] else "Đã nối lại",
        } for gap in report["gaps"]]
        with st.expander("Các khoảng gián đoạn"):
            st.dataframe(pd.DataFrame(gaps), hide_index=True, width="stretch")
