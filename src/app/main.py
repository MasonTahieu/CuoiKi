"""Screener and read-only viewer for demo and locally recorded data."""
import sqlite3
import time

import pandas as pd
import plotly.express as px
import streamlit as st

from src.app.journal_view import (
    connection_summary, read_journal_view, render_quality, sample_journal, snapshot_frame,
)
from src.config import ConfigurationError, load_settings
from src.providers import load_provider_settings
from src.data.synthetic import demo_events, demo_groups
from src.data.store import read_events, now, timestamp
from src.data.normalize import state_at, recorded_update_mode
from src.ranking.engine import rank_groups, FACTOR_NAMES

LABELS = {"score_momentum":"Động lượng", "score_liquidity":"Thanh khoản",
          "score_foreign":"Dòng tiền ngoại", "score_imbalance":"Cung–cầu"}


def live_refresh():
    with st.sidebar:
        interval = st.selectbox("Tự làm mới kho", [0, 10, 30],
                                format_func=lambda seconds: f"Mỗi {seconds} giây" if seconds else "Tắt")
        st.button("Đọc lại kho dữ liệu")
    if interval:
        next_refresh = time.monotonic() + interval

        @st.fragment(run_every=interval)
        def refresh_tick():
            if time.monotonic() >= next_refresh:
                st.rerun()

        refresh_tick()


def render():
    st.set_page_config(page_title="Bộ lọc VN30 và HNX30", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
    st.caption("VN30 & HNX30 SCREENER · DÀNH CHO NHÀ ĐẦU TƯ VÀ MÔI GIỚI")
    st.title("Bộ lọc cổ phiếu đa yếu tố")
    report = None
    events = []
    try:
        settings = load_settings()
        provider = load_provider_settings(settings.provider)
        with st.sidebar:
            st.header("Bộ lọc và thời điểm")
        if settings.mode == "live":
            live_refresh()

        selected_journal = None
        if settings.mode == "demo" and settings.provider == "ssi":
            with st.sidebar:
                demo_view = st.radio("Dữ liệu minh họa", ["Bảng điểm giả lập", "Nhật ký SSI mẫu"])
            if demo_view == "Nhật ký SSI mẫu":
                _, path, labels = sample_journal()
                selected_journal = read_journal_view(path, settings.mode, labels)
        elif settings.provider == "ssi" and provider.database.is_file():
            selected_journal = read_journal_view(provider.database, settings.mode)

        if selected_journal:
            run_info, report = selected_journal
            source = report["source"]
            cutoff = report["as_of"]
            last_recorded = run_info["last_received_at"]
            frame = snapshot_frame(report)
        else:
            if settings.mode == "demo":
                events = demo_groups() if settings.provider == "ssi" else demo_events()
            else:
                events = read_events(provider.database)
            if not events:
                raise ValueError("Lần thu thập được chọn chưa có sự kiện.")
            source = events[0]["source"]
            if settings.mode == "live" and source != settings.provider:
                raise ValueError("Chế độ live cần kho đúng nhà cung cấp được chọn.")
            if source not in {settings.provider, "synthetic"}:
                raise ValueError("Nguồn trong kho khác nhà cung cấp được chọn.")
            moments = sorted({e["received_at"] for e in events if e["channel"] == "stockInfo"}, key=timestamp)
            if not moments:
                st.info("Đang chờ snapshot cổ phiếu. Hãy kiểm tra nhật ký thu thập.")
                st.stop()
            last_recorded = moments[-1]
            if settings.mode == "live":
                cutoff = now()
            else:
                with st.sidebar:
                    cutoff = st.select_slider("Mốc phát lại (UTC+7)", options=moments, value=moments[-1])
            frame = state_at(events, cutoff, update_mode=recorded_update_mode(events, provider.update_mode))
    except (ConfigurationError, ValueError, OSError, sqlite3.Error) as error:
        if isinstance(error, sqlite3.Error):
            st.error("Không đọc được journal SQLite. Hãy kiểm tra kho dữ liệu.")
            st.stop()
        st.error(str(error))
        st.info("Mặc định APP_MODE=demo để chạy offline. Khi có quyền API, xem docs/CHUYEN_SANG_SSI.md.")
        st.stop()
    if source == "synthetic":
        st.warning("DỮ LIỆU GIẢ LẬP — mã DEMO hư cấu, không phải thành phần VN30/HNX30 hoặc dữ liệu thị trường thật.")
    else:
        st.info(f"DỮ LIỆU {source.upper()} ĐÃ LƯU · thời gian nhận tại máy, chưa khẳng định độ trễ từ sàn.")
    if source != "synthetic" and not provider.semantics_verified:
        st.warning("Chưa xác minh đơn vị và ngữ nghĩa tại P1: hiển thị dữ liệu, tạm khóa chấm điểm thật.")
    if report:
        connection_summary(report, settings.mode)
    if frame.empty:
        st.info("Đang chờ snapshot hoặc danh sách mã tại mốc chọn. Hãy chọn mốc khác nếu đang phát lại.")
        st.stop()
    with st.sidebar:
        st.caption(f"Chế độ: {settings.mode} · Nguồn: {source}")
        profile = st.selectbox("Trọng số", ["Cân bằng 25/25/25/25", "Ưu tiên động lượng 40/20/20/20"])
        weights = dict(zip(FACTOR_NAMES, [0.4,0.2,0.2,0.2] if profile.startswith("Ưu") else [0.25]*4))
    try:
        ranked = rank_groups(frame, weights=weights, semantics_verified=provider.semantics_verified)
    except ValueError as error:
        st.error(str(error))
        st.stop()
    if ranked.empty:
        st.info("Không có snapshot hợp lệ tại mốc chọn; có thể vừa ngắt kết nối hoặc qua ngày.")
        st.stop()
    with st.sidebar:
        groups = sorted(ranked["index_group"].unique())
        group = st.selectbox("Nhóm so sánh", groups, index=groups.index("VN30") if "VN30" in groups else 0)
        ranked = ranked.loc[ranked["index_group"].eq(group)]
        symbols = sorted(ranked["symbol"].tolist())
        chosen = st.multiselect("Mã cổ phiếu", symbols, default=symbols)
        minimum = st.slider("Điểm tổng tối thiểu", 0, 100, 0)
        st.caption("Lọc sau khi chấm điểm; không đổi nhóm so sánh.")
    view = ranked.loc[ranked["symbol"].isin(chosen)]
    if minimum:
        view = view.loc[view["total_score"].ge(minimum)]
    rank_count = int(ranked["rank"].count())
    analysis_time = timestamp(cutoff)
    a,b,c = st.columns(3)
    a.metric("Mã có hạng / nhóm", f"{rank_count} / {len(ranked)}")
    b.metric("Mã đang hiển thị", len(view))
    c.metric("Mốc phân tích (UTC+7)", analysis_time.strftime("%H:%M:%S"))
    st.caption(f"{group} · Ngày {analysis_time:%d/%m/%Y} · {ranked['cohort_size'].iloc[0]} mã đủ điều kiện · "
               f"Lần ghi cuối trong kho: {timestamp(last_recorded).strftime('%H:%M:%S %d/%m/%Y')} (UTC+7)")
    if report and all("NO_BASELINE" in row["reasons"] for row in report["rows"] if row["index_group"] == group):
        st.info("Đang chờ snapshot của lần kết nối này.")
    elif rank_count == 0:
        st.info("Nhóm chưa có mã được xếp hạng. Xem lý do trong bảng hoặc tab Chất lượng dữ liệu.")
    ranking_tab, detail_tab, quality_tab, method_tab = st.tabs(["Xếp hạng", "Chi tiết cổ phiếu", "Chất lượng dữ liệu", "Phương pháp"])
    with ranking_tab:
        if view.empty:
            st.info("Chưa chọn mã hoặc không có mã đạt bộ lọc.")
        else:
            display = ["symbol", "rank", "total_score", *LABELS, "quality_reason"]
            if report:
                display.append("data_warning")
            st.dataframe(view[display].rename(columns={"symbol":"Mã", "rank":"Hạng", "total_score":"Điểm tổng",
                "quality_reason":"Lý do chưa xếp hạng", "data_warning":"Cảnh báo", **LABELS}), hide_index=True, width="stretch",
                column_config={"Hạng":st.column_config.NumberColumn(format="%d"),
                    **{name:st.column_config.NumberColumn(format="%.2f") for name in ["Điểm tổng",*LABELS.values()]}})
            scored = view.dropna(subset=["total_score"])
            if not scored.empty:
                fig = px.bar(scored, x="symbol", y="total_score", color="total_score",
                    labels={"symbol":"Mã", "total_score":"Điểm tổng"}, range_y=[0,100],
                    title="So sánh điểm trong cùng nhóm")
                st.plotly_chart(fig, width="stretch")
            export = view.assign(**{f"weight_{factor}": value for factor, value in weights.items()})
            st.download_button("Tải bảng đang xem (CSV)", export.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"{source}_ranking.csv", mime="text/csv")
    with detail_tab:
        if not chosen:
            st.info("Chọn ít nhất một mã để xem chi tiết.")
        else:
            symbol = st.selectbox("Mã xem chi tiết", chosen)
            row = ranked.loc[ranked["symbol"].eq(symbol)].iloc[0]
            st.write(row.get("explanation", "Chưa đủ điều kiện xếp hạng"))
            if row["quality_reason"]:
                st.info(row["quality_reason"])
            if report and row["data_warning"]:
                st.warning(row["data_warning"])
            st.dataframe(pd.DataFrame({"Yếu tố":list(LABELS.values()), "Điểm":[row[k] for k in LABELS]}), hide_index=True)
            if report and pd.notna(row.get("closePrice")):
                st.metric("Giá khớp tại mốc chọn", f"{row['closePrice']:,.0f}")
            history = [{"Giờ nhận (UTC+7)":e["received_at"], "Giá (VNĐ)":e["payload"].get("closePrice")}
                for e in events if e["channel"] == "stockInfo" and e["payload"].get("symbol") == symbol
                and timestamp(e["received_at"]) <= analysis_time]
            if history:
                st.plotly_chart(px.line(pd.DataFrame(history), x="Giờ nhận (UTC+7)", y="Giá (VNĐ)", markers=True,
                    title=f"{symbol} · diễn biến giá đã ghi nhận · {source}"), width="stretch")
    with quality_tab:
        if report:
            render_quality(report, ranked, group)
        else:
            columns = {"symbol":"Mã", "received_at":"Giờ nhận", "age_seconds":"Tuổi snapshot (s)",
                       "session":"Phiên", "quality_reason":"Lý do chưa xếp hạng"}
            st.dataframe(ranked[[col for col in columns if col in ranked]].rename(columns=columns), hide_index=True)
            st.caption("Tuổi snapshot tính từ giờ nhận. Ngưỡng cũ cho từng trường bắt buộc là 60 giây.")
            logs = [{"time":e["received_at"], **e["payload"]} for e in events
                    if e["channel"] == "connection" and timestamp(e["received_at"]) <= analysis_time]
            if logs:
                st.dataframe(pd.DataFrame(logs), hide_index=True)
    with method_tab:
        st.caption(f"Trọng số hiện tại · {profile}")
        with st.expander("Thông tin lần tính"):
            st.text(f"Nguồn: {source}\nLần thu thập: {ranked['run'].iloc[0]}\n"
                    f"Phương pháp: {ranked['method_version'].iloc[0]}\nCấu hình: {ranked['config_id'].iloc[0]}\n"
                    f"Tập mã: {ranked['cohort_id'].iloc[0]}")
        st.markdown("""
**Mục đích:** thu hẹp danh sách để nghiên cứu tiếp, cho nhà đầu tư và môi giới.

- Động lượng: % thay đổi từ giá mở cửa đến giá khớp gần nhất.
- Thanh khoản: trung bình điểm phân vị của giá trị giao dịch, độ sâu ba mức giá và spread đảo chiều.
- Dòng tiền ngoại: (giá trị mua − bán nước ngoài) / tổng giá trị giao dịch.
- Cung–cầu: (khối lượng mua − bán) / tổng khối lượng chào ba mức giá.

Điểm phân vị 0–100 trên cùng nhóm đủ dữ liệu; hòa dùng hạng trung bình, mọi giá trị bằng nhau nhận 50.
Điểm tổng là tổng có trọng số. Tối thiểu 10 mã hợp lệ (quy tắc dự án, không phải yêu cầu của đề).
Không tự bỏ một yếu tố rồi chia lại trọng số. Không xếp hạng ngoài phiên LO, thiếu/cũ dữ liệu hoặc chưa xác minh nhà cung cấp.

Trọng số là baseline thử nghiệm. Thanh khoản có thể thiên về cổ phiếu lớn; các yếu tố có thể tương quan.
Mẫu giả lập chỉ kiểm tra phần mềm. Chưa có kiểm định dự báo, MA/RSI nhiều ngày hoặc dữ liệu lịch sử thực tế.
""")
    st.caption("SSI đang chờ đăng ký và xác minh dữ liệu thật. Công cụ học thuật; điểm không phải xác suất tăng giá hoặc khuyến nghị mua/bán.")
