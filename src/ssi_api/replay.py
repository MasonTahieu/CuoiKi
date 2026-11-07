"""Reconstruct a single SSI collector run from decoded journal events, never cached snapshots."""
import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import json
import math
from pathlib import Path

from src.config import PROJECT_ROOT
from src.data.normalize import NUMERIC
from src.data.ssi_journal import SSIJournal, JournalError
from src.data.ssi_quality import NEEDED, QualityPolicy, assess_member, group_coverage, policy_for_profile
from src.data.store import timestamp
from src.ssi_api.stream_collector import PatchState, validate_members

COUNTERS={"totalTradingVolume","totalTradingValue","foreignBuyVolume","foreignSellVolume"}
ALLOWED=set(NUMERIC)|{"symbol","marketCode","tradingDate","tradingSession","tradingStatus",
    "lastTradeVolume","ohlcClosePrice","foreignRoom","foreignRemain"}
CONTRACTS={("fcdata_v2","ssi-fcdata-v2-patch-1"):{"F","X","X-QUOTE","X-TRADE","R","B"},
           ("fastconnect_v3","ssi-v3-patch-1"):{"TRADE","QUOTE","ROOM","MARKET_FLAG","MASTER"}}
FOREIGN_TYPES={"R","ROOM"}


def validate_decoded(item,event):
    if item.get("source")!=event["source"]:
        raise JournalError("Nguồn trong decoder và journal mâu thuẫn; không đổi nhãn dữ liệu.")
    types=CONTRACTS.get((item.get("profile"),item.get("schema_version")))
    if types is None:
        raise JournalError("Chưa hỗ trợ phiên bản decoded journal này.")
    if item.get("message_type") not in types:
        raise JournalError("Loại thông điệp trong decoded journal không được hỗ trợ.")
    payload=item.get("payload")
    if (not isinstance(payload,dict) or not set(payload)<=ALLOWED or not isinstance(payload.get("symbol"),str)
            or not isinstance(item.get("metadata"),dict) or not isinstance(item.get("issues"),list)):
        raise JournalError("Decoded journal không khớp hợp đồng nội bộ.")
    if "source_at" not in item:
        raise JournalError("Decoded journal thiếu trường source_at.")
    if item["message_type"] in FOREIGN_TYPES and "foreign_value_estimated" not in item["metadata"]:
        raise JournalError("Decoded journal thiếu cờ ước tính giá trị ngoại.")
    if timestamp(item.get("received_at"))!=timestamp(event["received_at"]):
        raise JournalError("Timestamp nhận trong decoder và journal không khớp.")
    for key,value in payload.items():
        if value is None:continue
        if key in {"symbol","marketCode","tradingDate","tradingSession","tradingStatus"}:
            if not isinstance(value,str):raise JournalError("Kiểu trường metadata không hợp lệ.")
        elif isinstance(value,str) and value in {"ATO","ATC"} and key.startswith(("bidPrice","askPrice")):
            pass
        elif isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
            raise JournalError("Decoded journal chứa giá trị số không hợp lệ.")
    if any(not isinstance(i,dict) or not isinstance(i.get("code"),str) or not isinstance(i.get("field"),str) for i in item["issues"]):
        raise JournalError("Danh sách lỗi trường không hợp lệ.")


def replay(path,run=None,as_of=None,through_event_id=None,policy=None):
    policy=policy or QualityPolicy()
    with SSIJournal(path) as journal:
        if run is None:
            runs=journal.runs(1)
            if not runs:raise JournalError("Kho chưa có run của SSI collector; hãy chạy mẫu task 2 hoặc task 3.")
            run=runs[0]["run"]
        info=journal.describe(run)
        if through_event_id is not None:
            found=journal.db.execute("SELECT received_at FROM events WHERE id=? AND run=?",(through_event_id,run)).fetchone()
            if not found:raise JournalError("event_id phải thuộc đúng run được chọn.")
            default_time=found[0]
        else:
            default_time=info["last_received_at"]
        try:
            cutoff=timestamp(as_of or default_time)
        except (ValueError,TypeError,AttributeError):
            raise JournalError("Mốc phát lại phải là ISO8601 có múi giờ.") from None
        merger=None
        members={}
        epoch=None
        connection="unknown"
        stats=Counter()
        decreases={}
        gaps=[]
        gap_start=None
        gap_kind=None
        intervals=[]
        connected_start=None
        last_id=None
        profiles=set()
        def end_connected(at):
            nonlocal connected_start
            if connected_start is not None:
                intervals.append({"start":connected_start.isoformat(),"end":at.isoformat(),
                    "seconds":max(0,(at-connected_start).total_seconds()),"open_ended":False})
                connected_start=None
        def start_gap(at,kind):
            nonlocal gap_start,gap_kind
            if gap_start is None:gap_start,gap_kind=at,kind
        for event in journal.events(run,through_event_id):
            try:at=timestamp(event["received_at"])
            except (ValueError,TypeError,AttributeError):raise JournalError("Journal có timestamp nhận không hợp lệ.") from None
            if at>cutoff or at.date()!=cutoff.date():continue
            last_id=event["event_id"]
            stats["journal_events"]+=1
            kind,item=event["channel"],event["payload"]
            if kind in {"ssiRaw","ssiMerged"}:
                stats[kind]+=1
                continue  # cached snapshots/raw are never the replay authority
            if kind=="connection":
                state=item.get("state")
                incoming=item.get("connection_epoch")
                if item.get("profile"):profiles.add(item["profile"])
                if type(incoming) is not int or incoming<1:
                    raise JournalError("Journal thiếu connection_epoch hợp lệ; không dùng pipeline NEO/REST thay thế.")
                if state=="connecting":
                    end_connected(at)
                    if epoch is not None:start_gap(at,"reinitializing")
                    epoch=incoming
                    merger=None
                    decreases={}
                    connection="connecting"
                    stats["connection_attempts"]+=1
                elif incoming!=epoch:
                    stats["epoch_mismatch"]+=1
                elif state=="connected":
                    if merger is None:
                        connection="awaiting_bootstrap"
                    else:
                        connection="connected"
                        connected_start=at
                        stats["connections"]+=1
                        if gap_start is not None:
                            gaps.append({"kind":gap_kind,"start":gap_start.isoformat(),"end":at.isoformat(),
                                "seconds":max(0,(at-gap_start).total_seconds()),"open_ended":False})
                            gap_start=gap_kind=None
                elif state in {"disconnected","auth_failed","adapter_error"}:
                    end_connected(at)
                    start_gap(at,state)
                    connection=state
                    merger=None
                    decreases={}
                elif state=="stopped":
                    end_connected(at)
                    connection="stopped"  # keep values for inspection, but block data_usable
                elif state=="decode_error":stats["decode_errors"]+=1
                continue
            if kind=="universe":
                if item.get("connection_epoch")!=epoch or connection not in {"connecting","connected"}:
                    raise JournalError("Universe không thuộc lần bootstrap hiện hành.")
                try:members=validate_members(item.get("members"))
                except ValueError:raise JournalError("Danh sách nhóm trong journal không hợp lệ.") from None
                merger=PatchState(list(members.values()),cutoff.date())
                decreases={}
                continue
            if kind!="ssiDecoded":continue
            stats["decoded"]+=1
            try:validate_decoded(item,event)
            except (TypeError,AttributeError,KeyError,ValueError) as error:
                if isinstance(error,JournalError):raise
                raise JournalError("Decoded journal không đủ metadata hợp lệ.") from None
            if item.get("connection_epoch")!=epoch or merger is None or connection!="connected":
                stats["inactive_epoch"]+=1
                continue
            source_time=None
            if item.get("source_at"):
                try:source_time=timestamp(item["source_at"])
                except (ValueError,TypeError,AttributeError):raise JournalError("Thời gian nguồn trong journal không hợp lệ.") from None
                if source_time>cutoff:
                    stats["source_after_cutoff"]+=1
                    continue
            symbol=item["payload"]["symbol"]
            previous=deepcopy(merger.states.get(symbol))
            state,outcome=merger.apply(item)
            stats[outcome]+=1
            if previous and source_time is not None and outcome in {"merged","no_new_fields"}:
                old_clocks=previous["field_updated_at"]
                superseded=[key for key in item["payload"] if key in old_clocks and timestamp(old_clocks[key])>source_time]
                stats["late_fields_ignored"]+=len(superseded)
                if superseded:stats["late_messages"]+=1
            if state is None:continue
            if previous:
                for key in state["changed_fields"]:
                    before,after=previous["payload"].get(key),state["payload"].get(key)
                    if key in COUNTERS and before is not None and after is not None and after<before:
                        decreases.setdefault(symbol,set()).add(key)
        if gap_start is not None:
            gaps.append({"kind":gap_kind,"start":gap_start.isoformat(),"end":cutoff.isoformat(),
                "seconds":max(0,(cutoff-gap_start).total_seconds()),"open_ended":True})
        if connected_start is not None:
            intervals.append({"start":connected_start.isoformat(),"end":cutoff.isoformat(),
                "seconds":max(0,(cutoff-connected_start).total_seconds()),"open_ended":True})
        if len(profiles)>1:
            raise JournalError("Một run không được trộn nhiều phiên bản SSI.")
        profile=next(iter(profiles),"fcdata_v2")
        policy=policy_for_profile(policy,profile)
        rows=[assess_member(member,merger.states.get(symbol) if merger else None,cutoff,connection,policy,decreases.get(symbol,()))
              for symbol,member in sorted(members.items())]
        lags=[v for row in rows for v in row["recorded_lag_seconds"].values()]
        return {"schema_version":"ssi-replay-quality-v1","source":info["source"],"profile":profile,"run":run,"as_of":cutoff.isoformat(),
            "through_event_id":through_event_id,"last_applied_event_id":last_id,"policy":asdict(policy),
            "last_recorded_connection_state":connection,"connection_epoch":epoch,"statistics":dict(stats),
            "rows":rows,"group_coverage":group_coverage(rows),"gaps":gaps,"connection_intervals":intervals,
            "recorded_connected_seconds":sum(i["seconds"] for i in intervals),
            "recorded_lag_range_seconds":{"min":min(lags),"max":max(lags)} if lags else None,
            "live_verified":False,"ranking_ready":False}


def export_report(report,directory):
    import csv
    import hashlib
    folder=Path(directory)
    serialized=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)
    folder.mkdir(parents=True,exist_ok=True)
    def csv_file(name,rows,columns):
        with (folder/name).open("w",encoding="utf-8-sig",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
    snapshot=[]
    fields=[]
    for row in report["rows"]:
        snapshot.append({"source":report["source"],"run":report["run"],"as_of":report["as_of"],
            "symbol":row["symbol"],"index_group":row["index_group"],"marketCode":row["marketCode"],
            "data_usable":row["data_usable"],"ranking_ready":False,"reasons":";".join(row["reasons"]),
            "warnings":";".join(row["warnings"]),**{k:row["payload"].get(k) for k in NUMERIC}})
        for key in sorted(set(NEEDED)|set(row["field_updated_at"])):
            fields.append({"symbol":row["symbol"],"index_group":row["index_group"],"field":key,
                "required":key in NEEDED,"source_at":row["field_updated_at"].get(key),
                "received_at":row["field_received_at"].get(key),"source_age_seconds":row["source_age_seconds"].get(key),
                "receive_age_seconds":row["receive_age_seconds"].get(key),"recorded_lag_seconds":row["recorded_lag_seconds"].get(key),
                "message_type":row["field_message_type"].get(key),"issues":";".join(row["field_issues"].get(key,[])),
                "stale":key in row["stale_fields"],"missing":key in row["missing_fields"],
                "invalid":key in row["invalid_fields"],"lagging":key in row["lagging_fields"]})
    columns=["source","run","as_of","symbol","index_group","marketCode","data_usable","ranking_ready","reasons","warnings",*NUMERIC]
    csv_file("snapshot.csv",snapshot,columns)
    csv_file("field_quality.csv",fields,["symbol","index_group","field","required","source_at","received_at","message_type",
        "issues","source_age_seconds","receive_age_seconds","recorded_lag_seconds","stale","missing","invalid","lagging"])
    csv_file("gaps.csv",report["gaps"],["kind","start","end","seconds","open_ended"])
    (folder/"quality.json").write_text(serialized,encoding="utf-8")
    files=["snapshot.csv","field_quality.csv","gaps.csv","quality.json"]
    manifest={"source":report["source"],"run":report["run"],"as_of":report["as_of"],"policy":report["policy"],
        "files":{name:hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in files}}
    (folder/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")


def main():
    import sys
    if hasattr(sys.stdout,"reconfigure"):sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser(description="Phát lại journal SSI collector và xuất chất lượng, hoàn toàn cục bộ.")
    parser.add_argument("--db",type=Path,default=PROJECT_ROOT/"runtime"/"ssi.sqlite")
    parser.add_argument("--run")
    parser.add_argument("--as-of")
    parser.add_argument("--event-id",type=int)
    parser.add_argument("--list-runs",action="store_true")
    parser.add_argument("--out",type=Path,default=PROJECT_ROOT/"runtime"/"ssi-replay-report")
    args=parser.parse_args()
    try:
        if args.list_runs:
            with SSIJournal(args.db) as journal:result=journal.runs()
        else:
            result=replay(args.db,args.run,args.as_of,args.event_id)
            export_report(result,args.out)
            result={k:result[k] for k in ("source","run","as_of","last_recorded_connection_state","statistics","group_coverage")}
            result["output"]=str(args.out)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,OSError) as error:
        print(str(error))
        return 2


if __name__=="__main__":raise SystemExit(main())
