"""Create an offline collector journal, replay checkpoints and a human-readable review."""
import json

from src.config import PROJECT_ROOT
from src.data.ssi_journal import BufferedSink, SSIJournal
from src.data.store import EventStore, timestamp
from src.ssi_api.collect_sample import scenario
from src.ssi_api.fake_stream import FakeClock, FakeFactory
from src.ssi_api.replay import export_report, replay
from src.ssi_api.stream_collector import Frame, collect_stream


def save_sample(database, members, scripts, *, seconds=30, max_messages=15):
    clock=FakeClock()
    store=EventStore(database)
    sink=BufferedSink(store,batch_size=16)
    try:
        result=collect_stream(FakeFactory(members,scripts,clock),sink,seconds=seconds,max_messages=max_messages,
            clock=clock.monotonic,sleep=clock.sleep,wall_now=clock.wall_now)
        sink.flush()
        return result
    finally:
        store.close()


def stale_scenario():
    members,scripts=scenario()
    initial=scripts[0][:4]  # X+R for each member
    origin=timestamp("2026-11-04T10:00:00+07:00")
    from datetime import timedelta
    for second in (10,20,30,40,50,63):
        received=origin+timedelta(seconds=second)
        source=received-timedelta(seconds=1)
        for member in members:
            initial.append(Frame({"DataType":"X-QUOTE","Content":{"Symbol":member["symbol"],
                "Exchange":member["marketCode"],"TradingDate":"04/11/2026","Time":source.strftime("%H:%M:%S"),
                "BidPrice1":19990}},received.isoformat()))
    return members,[initial]


REASONS={
    "CONNECTION_NOT_ACTIVE":"Kết nối không hoạt động tại mốc chọn",
    "NO_BASELINE":"Chưa có dữ liệu nền của lần kết nối hiện tại",
    "MISSING_FIELDS":"Thiếu trường",
    "INVALID_VALUES":"Giá trị không hợp lệ",
    "STALE_FIELDS":"Trường quá cũ",
    "FIELD_TIME_MISSING":"Thiếu dấu thời gian",
    "EXCESS_RECORDED_LAG":"Chênh thời gian nguồn–nhận vượt ngưỡng",
    "SESSION_NOT_LO":"Chưa xác nhận phiên LO",
    "STATUS_NOT_NORMAL":"Mã không ở trạng thái giao dịch bình thường",
    "COUNTER_DECREASE":"Số liệu lũy kế giảm bất thường",
}


def main():
    output=PROJECT_ROOT/"evidence"/"task3"
    output.mkdir(parents=True,exist_ok=True)
    database=PROJECT_ROOT/"runtime"/"task3-synthetic.sqlite"
    members,scripts=scenario()
    collected=save_sample(database,members,scripts)
    run=collected["run"]
    checkpoints=[]
    for name,second in (
        ("Dữ liệu ban đầu", "01"),
        ("Một trường bid bị null", "03"),
        ("Đang mất kết nối", "06.500000"),
        ("Mới kết nối lại, chỉ nhận Trade", "09"),
        ("Đã nhận lại X+R của hai mã", "13"),
    ):
        checkpoints.append({"name":name,"report":replay(database,run,f"2026-11-04T10:00:{second}+07:00")})
    # A cursor distinguishes F/HALT from the stopped marker with the same timestamp.
    with SSIJournal(database) as journal:
        last_decoded=max(e["event_id"] for e in journal.events(run) if e["channel"]=="ssiDecoded")
    checkpoints.append({"name":"DEMO02 tạm ngừng giao dịch, trước khi collector dừng",
        "report":replay(database,run,through_event_id=last_decoded)})
    checkpoints.append({"name":"Collector đã dừng","report":replay(database,run)})
    export_report(checkpoints[4]["report"],output/"export")

    stale_members,stale_scripts=stale_scenario()
    stale_collected=save_sample(database,stale_members,stale_scripts,seconds=65,max_messages=100)
    stale_report=replay(database,stale_collected["run"],"2026-11-04T10:01:03+07:00")
    checkpoints.append({"name":"Luồng vẫn có quote, khối ngoại đã quá 60 giây","report":stale_report})
    export_report(stale_report,output/"stale-export")
    (output/"checkpoints.json").write_text(json.dumps(checkpoints,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")

    lines=["# Task 3 — Kết quả lưu trữ, phát lại và chất lượng dữ liệu", "",
        "**Hoàn toàn giả lập (`source=synthetic`), không gọi mạng và không dùng khóa SSI/NEO.**", "",
        "Hai mã hư cấu DEMO01 và DEMO02 trong nhóm VN30; không phải thành phần VN30 thật.",
        "`data_usable` là kết quả kiểm tra dữ liệu tại mốc chọn. Báo cáo replay dùng `ranking_ready=false`.", "",
        "## 1. Kiểm tra theo mốc", "",
        "| Tình huống | Mốc giờ +07:00 | Trạng thái ghi nhận | VN30 dùng được |",
        "|---|---|---|---|"]
    for checkpoint in checkpoints:
        report=checkpoint["report"]
        coverage=report["group_coverage"]
        counts=[f'{coverage[g]["data_usable"]}/{coverage[g]["members"]}' for g in ("VN30",)]
        lines.append(f'| {checkpoint["name"]} | {report["as_of"].split("T")[1]} | {report["last_recorded_connection_state"]} | {counts[0]} |')
    lines.extend(["", "Độ phủ được tính trên danh sách bootstrap của run này (2 mã), không phải độ phủ 30 mã thực tế.",
        "Các mốc phát lại không lấy giá/trường xuất hiện sau mốc chọn. Bản ghi `ssiMerged` chỉ để đối chiếu, không quyết định trạng thái replay.",
        "", "## 2. Những kết quả cần kiểm tra", "",
        "- 10:00:01: giá DEMO01 là **20.000**, chưa dùng giá ở các mốc sau.",
        "- 10:00:03: `bidVol1=null` làm DEMO01 thiếu trường; DEMO02 vẫn đủ dữ liệu.",
        "- 10:00:06,5: mất kết nối; dữ liệu nền cũ bị xóa. Gap đang mở được ghi nhận 0,5 giây tại mốc này.",
        "- 10:00:09: đã kết nối lại nhưng chỉ có giá Trade; vẫn thiếu mở cửa, sổ lệnh và khối ngoại.",
        "- 10:00:13: cả hai mã qua kiểm tra dữ liệu; gap hoàn tất dài **1 giây**. Cờ khối ngoại ước tính của mã HOSE vẫn được giữ.",
        "- 10:00:14, ngay sau F: DEMO02 bị HALT nên bị chặn; DEMO01 vẫn qua kiểm tra. Dùng event ID để phân biệt với sự kiện dừng cùng giây.",
        "- Sau sự kiện dừng: vẫn xem được snapshot lịch sử, nhưng dữ liệu bị chặn vì kết nối đã dừng.", "",
        "## 3. Trường mới không làm mới các trường khác", "",
        "Run thứ hai giữ luồng hoạt động bằng các quote cách nhau tối đa 13 giây. Tại 10:01:03:", "",
        "| Mã | Tuổi giá bid 1 | Tuổi khối ngoại mua | Chênh nguồn–nhận của bid 1 | Lý do chặn |", "|---|---|---|---|---|"])
    for row in stale_report["rows"]:
        reasons="; ".join(REASONS.get(r,r) for r in row["reasons"])
        lines.append(f'| {row["symbol"]} | {row["source_age_seconds"]["bidPrice1"]:g} giây | {row["source_age_seconds"]["foreignBuyValue"]:g} giây | {row["recorded_lag_seconds"]["bidPrice1"]:g} giây | {reasons} |')
    lines.extend(["", "Ngưỡng mặc định: trường động tối đa 60 giây; chênh nguồn–nhận tối đa 10 giây. Đây là quy ước thử nghiệm, chưa phải SLA của SSI.",
        "Chênh thời gian ghi nhận có thể bao gồm lệch đồng hồ; không thể coi đó là phép đo độ trễ mạng thuần túy.", "",
        "## 4. Tệp để xem", "",
        "- [Báo cáo chất lượng lúc 10:00:13](export/quality.json)",
        "- [Snapshot CSV](export/snapshot.csv) · [Chất lượng từng trường](export/field_quality.csv) · [Gap](export/gaps.csv)",
        "- [Báo cáo dữ liệu cũ](stale-export/quality.json)",
        "- [Toàn bộ mốc kiểm tra](checkpoints.json)",
        "- [Hướng dẫn task 3](../../docs/TASK_3_LUU_TRU_REPLAY_CHAT_LUONG.md)", "",
        "Mỗi thư mục xuất có manifest SHA-256 để đối chiếu nội dung; đây không phải chữ ký xác nhận của SSI.",
        "Kho SQLite và các tệp mẫu được tạo lại bằng `python -X utf8 -m src.ssi_api.replay_sample`.",
        "Mỗi lần chạy thêm run riêng; không ghi đè hoặc trộn dữ liệu thật.", "",
        "Phần kiểm chứng công thức và xếp hạng giả lập có bảng mẫu riêng. [Kết quả mẫu task 4](../task4/KET_QUA_MAU.md)", ""])
    (output/"KET_QUA_MAU.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps({"source":"synthetic","network_called":False,"database":str(database),
        "runs":[run,stale_collected["run"]],"checkpoints":len(checkpoints),
        "review":str(output/"KET_QUA_MAU.md")},ensure_ascii=False,indent=2))


if __name__=="__main__":main()
