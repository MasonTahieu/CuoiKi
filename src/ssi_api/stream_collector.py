"""Transport-independent collector for FCData v2 and FastConnect V3 frames.

The factory declares its profile; the matching decoder, subscription plan and raw-retention
rule are chosen here. Sinks preserve decoder metadata; the legacy stockInfo replay is not used.
"""
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from datetime import timedelta
import hashlib
import json
import math
import re
import time
from typing import Protocol
import uuid

from src.data.normalize import REQUIRED
from src.data.store import timestamp
from src.ssi_api.decoder import decode_fcdata, DecodeError, _object
from src.ssi_api import v3_decoder


class StreamDisconnected(RuntimeError):
    pass


class StreamAuthFailed(RuntimeError):
    pass


class _StreamAdapterError(RuntimeError):
    pass


def _call_adapter(action, *args):
    try:
        return action(*args)
    except (StreamDisconnected, StreamAuthFailed):
        raise
    except Exception:
        # Only transport calls cross this boundary. Sink and decoder errors keep their own behavior.
        raise _StreamAdapterError() from None


@dataclass(frozen=True)
class Frame:
    raw: object
    received_at: str


class Stream(Protocol):
    def connect(self): ...
    def subscribe(self, channels: tuple[str, ...]): ...
    def receive(self, timeout: float) -> Frame | None: ...
    def close(self): ...


class Factory(Protocol):
    source: str
    def create(self) -> Stream: ...
    def bootstrap(self) -> list[dict]: ...
    # Optional: ``profile`` ("fcdata_v2" default or "fastconnect_v3") and ``topics(members)``.


PROFILES={"fcdata_v2","fastconnect_v3"}


def _profile_tools(factory):
    profile=getattr(factory,"profile","fcdata_v2")
    if profile not in PROFILES:
        raise ValueError("Profile transport không được hỗ trợ.")
    if profile=="fastconnect_v3":
        decode=lambda raw,received_at,source:v3_decoder.decode_v3(raw,received_at=received_at,source=source)
        keep=lambda frame,decoded:v3_decoder.retained_raw(frame.raw,decoded)
        expand=v3_decoder.fan_out
        plan=getattr(factory,"topics",None) or v3_subscription_plan
    else:
        decode=lambda raw,received_at,source:decode_fcdata(raw,received_at=received_at,source=source)
        keep=market_raw
        expand=lambda decoded,members:[decoded]
        plan=getattr(factory,"topics",None) or subscription_plan
    return profile,decode,keep,expand,plan


def validate_members(members):
    if not isinstance(members,list) or not members:
        raise ValueError("Cần danh sách thành phần nhóm, không dùng danh sách rỗng.")
    result={}
    for member in members:
        if not isinstance(member,dict):
            raise ValueError("Thành phần nhóm phải là object.")
        symbol=member.get("symbol")
        if not isinstance(symbol,str) or not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{0,31}",symbol):
            raise ValueError("Mã trong danh sách nhóm không hợp lệ.")
        if symbol in result:
            raise ValueError("Trùng mã trong danh sách nhóm.")
        expected={"VN30":"HOSE"}.get(member.get("index_group"))
        if not expected or member.get("marketCode")!=expected:
            raise ValueError("Nhóm/sàn không khớp VN30–HOSE.")
        result[symbol]={k:member[k] for k in ("symbol","index_group","marketCode")}
    return result


def subscription_plan(members):
    symbols="-".join(sorted(validate_members(members)))
    # Subscription intent only. A live adapter must implement how its SDK combines channels.
    return tuple(f"{kind}:{symbols}" for kind in ("X","F","X-Quote","X-Trade","R","B"))


def v3_subscription_plan(members):
    """Basket fan-out topics (``trade.VN30@*``) plus the all-board session flag."""
    groups=sorted({m["index_group"] for m in validate_members(members).values()})
    return tuple(f"{kind}.{group}@*" for group in groups for kind in ("trade","quote","room"))+("market.flag",)


def market_raw(frame,decoded):
    """Retain only fields consumed by decoder, never arbitrary raw string bodies."""
    outer=_object(frame.raw)
    content=next((v for k,v in outer.items() if k.lower()=="content"),outer)
    content=_object(content)
    allowed={"symbol","rtype","datatype","tradingdate","time","tradingtime"}
    allowed.update(alias for aliases in decoded["field_sources"].values() for alias in aliases)
    targets={alias:target for target,aliases in decoded["field_sources"].items() for alias in aliases}
    clean={}
    for key,value in content.items():
        if key.lower() not in allowed:
            continue
        target=targets.get(key.lower())
        if ((target and decoded["payload"].get(target) is None) or isinstance(value,(dict,list))
                or isinstance(value,float) and not math.isfinite(value)):
            value=None
        clean[key]=value
    return {"DataType":decoded["message_type"],"Content":clean}


class PatchState:
    """Merge by field source time, scoped to a single connection and calendar day."""
    def __init__(self,members,day,dedup_limit=4096):
        self.members=validate_members(members)
        self.day=day
        self.states={}
        self.seen=OrderedDict()
        self.dedup_limit=dedup_limit

    def apply(self,decoded):
        payload=decoded["payload"]
        symbol=payload["symbol"]
        if symbol not in self.members:
            return None,"outside_universe"
        member=self.members[symbol]
        if "marketCode" in payload and payload["marketCode"]!=member["marketCode"]:
            return None,"market_mismatch"
        if not decoded["source_at"]:
            return None,"source_time_missing"
        at,received=timestamp(decoded["source_at"]),timestamp(decoded["received_at"])
        if at.date()!=self.day or received.date()!=self.day:
            return None,"wrong_day"
        if at>received+timedelta(seconds=5):
            return None,"source_time_in_future"
        digest=hashlib.sha256(json.dumps([decoded["message_type"],decoded["source_at"],payload],
            sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
        if digest in self.seen:
            return None,"duplicate"
        self.seen[digest]=None
        if len(self.seen)>self.dedup_limit:
            self.seen.popitem(last=False)
        previous=self.states.get(symbol)
        state=deepcopy(previous) if previous else {"symbol":symbol,"index_group":member["index_group"],
            "marketCode":member["marketCode"],"payload":{"symbol":symbol,"marketCode":member["marketCode"]},
            "field_updated_at":{},"field_received_at":{},"field_message_type":{},"field_issues":{},
            "metadata":{},"last_received_at":decoded["received_at"]}
        changed=[]
        for key,value in payload.items():
            if key in {"symbol","marketCode","tradingDate"}:
                continue
            old_at=state["field_updated_at"].get(key)
            if old_at and at<timestamp(old_at):
                continue
            state["payload"][key]=value  # null intentionally invalidates the old value
            state["field_updated_at"][key]=at.isoformat()
            state["field_received_at"][key]=decoded["received_at"]
            state["field_message_type"][key]=decoded["message_type"]
            state["field_issues"][key]=[i["code"] for i in decoded["issues"] if i["field"]==key]
            changed.append(key)
        if not changed:
            return None,"no_new_fields"
        state["payload"]["tradingDate"]=at.strftime("%d/%m/%Y")
        if decoded["message_type"] in {"R","ROOM"} and any(k.startswith("foreign") for k in changed):
            state["metadata"]["foreign_value_estimated"]=decoded["metadata"]["foreign_value_estimated"]
        if "totalTradingValue" in changed:
            derived=decoded["metadata"].get("derived_fields",{}).get("totalTradingValue")
            fields=dict(state["metadata"].get("derived_fields",{}))
            if derived:fields["totalTradingValue"]=derived
            else:fields.pop("totalTradingValue",None)
            state["metadata"]["derived_fields"]=fields
        state["last_received_at"]=max(state["last_received_at"],decoded["received_at"])
        needed=REQUIRED+["tradingSession","tradingStatus"]
        state["missing_fields"]=[key for key in needed if state["payload"].get(key) is None]
        state["fields_complete"]=not state["missing_fields"]
        # Completeness is not permission to rank: freshness, method and live validation belong to later tasks.
        state["ranking_ready"]=False
        state["changed_fields"]=changed
        self.states[symbol]=state
        return deepcopy(state),"merged"


# The SDK reopens the socket about every 14 minutes, ahead of the 15-minute token (measured 09/11/2026).
# That is routine: only drops in a row count towards max_reconnects and lengthen the wait.
STABLE_SECONDS=60
MAX_RECONNECT_WAIT=30


def collect_stream(factory: Factory, sink, *, seconds=60, max_messages=10000, max_reconnects=3,
                   idle_seconds=15, clock=time.monotonic, sleep=time.sleep, wall_now=None):
    """Bounded collection; sink receives existing EventStore append-style keyword args."""
    if factory.source not in {"synthetic","ssi"}:
        raise ValueError("Nguồn transport phải được khai báo rõ.")
    profile,decode,keep,expand,plan=_profile_tools(factory)
    if seconds<=0 or max_messages<1 or max_reconnects<0 or idle_seconds<=0:
        raise ValueError("Giới hạn collector không hợp lệ.")
    from src.data.store import now
    wall_now=wall_now or now
    run=f"{factory.source}-stream-"+uuid.uuid4().hex
    deadline=clock()+seconds
    counters={k:0 for k in ("received","decoded","merged","duplicate","rejected","decode_errors","reconnects")}
    merger=None
    epoch=0
    reason="duration_limit"
    failures=0
    healthy_since=None
    def emit(channel,payload,at=None):
        sink(source=factory.source,run=run,received_at=at or wall_now(),channel=channel,payload=payload)
    def status(value):
        emit("connection",{"state":value,"connection_epoch":epoch,"update_mode":"patch","profile":profile})
    while clock()<deadline and counters["received"]<max_messages:
        stream=None
        epoch+=1
        merger=None  # never retain a baseline across connection gaps
        healthy_since=None
        try:
            status("connecting")
            members=_call_adapter(factory.bootstrap)
            day=timestamp(wall_now()).date()
            merger=PatchState(members,day)
            emit("universe",{"members":list(merger.members.values()),"connection_epoch":epoch})
            stream=_call_adapter(factory.create)
            _call_adapter(stream.connect)
            _call_adapter(stream.subscribe, tuple(plan(members)))
            status("connected")
            idle_start=clock()
            while clock()<deadline and counters["received"]<max_messages:
                frame=_call_adapter(stream.receive, min(1,max(0,deadline-clock())))
                if frame is None:
                    if clock()-idle_start>=idle_seconds:
                        raise StreamDisconnected("idle")
                    sleep(min(.05,max(0,deadline-clock())))
                    continue
                idle_start=clock()
                healthy_since=clock() if healthy_since is None else healthy_since
                counters["received"]+=1
                if not isinstance(frame,Frame):
                    raise ValueError("Transport trả dữ liệu khác Frame.")
                if timestamp(frame.received_at).date()!=day:
                    raise StreamDisconnected("day_changed")
                try:
                    decoded=decode(frame.raw,frame.received_at,factory.source)
                except DecodeError:
                    counters["decode_errors"]+=1
                    emit("connection",{"state":"decode_error","connection_epoch":epoch},frame.received_at)
                    continue
                counters["decoded"]+=1
                emit("ssiRaw",{"connection_epoch":epoch,"message":keep(frame,decoded)},frame.received_at)
                for item in expand(decoded,merger.members):
                    item={k:v for k,v in item.items() if k!="scope"}
                    emit("ssiDecoded",{**item,"connection_epoch":epoch},frame.received_at)
                    state,outcome=merger.apply(item)
                    if outcome=="merged":
                        counters["merged"]+=1
                        emit("ssiMerged",{**state,"connection_epoch":epoch},frame.received_at)
                    else:
                        counters["duplicate" if outcome=="duplicate" else "rejected"]+=1
                        emit("connection",{"state":outcome,"connection_epoch":epoch},frame.received_at)
            reason="message_limit" if counters["received"]>=max_messages else "duration_limit"
            status("stopped")
            break
        except _StreamAdapterError:
            merger=None
            status("adapter_error")
            reason="adapter_error"
            break
        except StreamAuthFailed:
            merger=None
            status("auth_failed")
            reason="auth_failed"
            break
        except StreamDisconnected:
            merger=None
            status("disconnected")
            if healthy_since is not None and clock()-healthy_since>=STABLE_SECONDS:
                failures=0
            if failures>=max_reconnects or clock()>=deadline:
                reason="reconnect_limit" if failures>=max_reconnects else "duration_limit"
                break
            delay=min(2**failures,MAX_RECONNECT_WAIT,max(0,deadline-clock()))
            failures+=1
            counters["reconnects"]+=1
            sleep(delay)
        finally:
            if stream is not None:
                stream.close()
    return {"source":factory.source,"profile":profile,"run":run,"stop_reason":reason,"counters":counters,
            "states":deepcopy(merger.states) if merger else {},"network_called":False if factory.source=="synthetic" else None}
