"""As-of quality gates for SSI collector snapshots. No scores or investment claims."""
from dataclasses import asdict,dataclass
from datetime import time
import math
from src.data.normalize import REQUIRED
from src.data.store import timestamp

NEEDED=tuple(REQUIRED)+("tradingSession","tradingStatus")
SAME_DAY={"openPrice","tradingSession","tradingStatus"}
THRESHOLDS=("max_age_seconds","max_recorded_lag_seconds","max_clock_skew_seconds")
# Order-matching timetable of the cash market (HOSE/HNX trading rules). Used only when the feed
# sent no session flag for the connection, and always reported as a SESSION_FROM_SCHEDULE warning.
SCHEDULE={
    "HOSE":((time(9,0),"ATO"),(time(9,15),"LO"),(time(11,30),"BREAK"),(time(13,0),"LO"),(time(14,30),"ATC"),(time(14,45),"PT"),(time(15,0),"C")),
    "HNX":((time(9,0),"LO"),(time(11,30),"BREAK"),(time(13,0),"LO"),(time(14,30),"ATC"),(time(14,45),"PT"),(time(15,0),"C")),
}


def scheduled_session(market,at):
    """Session by the published timetable; weekends and unknown boards are closed/unknown."""
    if market not in SCHEDULE or at.weekday()>=5:
        return "C" if market in SCHEDULE else None
    session="C"
    for start,name in SCHEDULE[market]:
        if at.time()>=start:
            session=name
    return session


@dataclass(frozen=True)
class QualityPolicy:
    max_age_seconds: float=60
    max_recorded_lag_seconds: float=10
    max_clock_skew_seconds: float=5
    # FCData v2 sends a per-symbol status; FastConnect V3 does not, so V3 replays relax this.
    require_symbol_status: bool=True
    # "none": a missing session flag blocks ranking. "schedule": fall back to the timetable.
    session_fallback: str="none"

    def __post_init__(self):
        if any(isinstance(getattr(self,k),bool) or not isinstance(getattr(self,k),(int,float))
               or not math.isfinite(getattr(self,k)) or getattr(self,k)<0 for k in THRESHOLDS):
            raise ValueError("Các ngưỡng chất lượng phải hữu hạn và không âm.")
        if not isinstance(self.require_symbol_status,bool) or self.session_fallback not in {"none","schedule"}:
            raise ValueError("Chính sách trạng thái/phiên không hợp lệ.")

    def needed(self):
        return tuple(k for k in NEEDED if self.require_symbol_status or k!="tradingStatus")


def policy_for_profile(policy,profile):
    """V3 has no per-symbol status and broadcasts session flags only on change."""
    from dataclasses import replace
    if profile=="fastconnect_v3":
        return replace(policy,require_symbol_status=False,session_fallback="schedule")
    return policy


def assess_member(member,state,as_of,connection_state,policy,counter_issues=()):
    cutoff=timestamp(as_of)
    payload=state["payload"] if state else {}
    missing,invalid,stale,time_missing,clock_skew,lagging=[],[],[],[],[],[]
    ages,receive_ages,lags={}, {}, {}
    field_issues=state.get("field_issues",{}) if state else {}
    needed=policy.needed()
    session=payload.get("tradingSession")
    session_basis="feed" if session is not None else None
    if session is None and policy.session_fallback=="schedule" and state is not None:
        session,session_basis=scheduled_session(member.get("marketCode"),cutoff),"schedule"
    for key in needed:
        value=payload.get(key)
        if key=="tradingSession" and session_basis=="schedule":
            continue
        if value is None:
            missing.append(key)
            if "INVALID_NUMBER" in field_issues.get(key,[]):invalid.append(key)
            continue
        if key not in {"tradingSession","tradingStatus"}:
            if (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value)
                    or value<0 or ("Price" in key and value<=0)):
                invalid.append(key)
        source_at=state.get("field_updated_at",{}).get(key)
        received_at=state.get("field_received_at",{}).get(key)
        if not source_at or not received_at:
            time_missing.append(key)
            continue
        source_time,receive_time=timestamp(source_at),timestamp(received_at)
        ages[key]=(cutoff-source_time).total_seconds()
        receive_ages[key]=(cutoff-receive_time).total_seconds()
        lags[key]=(receive_time-source_time).total_seconds()
        if lags[key]<0:
            clock_skew.append(key)
        if (source_time.date()!=cutoff.date() or receive_time.date()!=cutoff.date() or ages[key]<0 or receive_ages[key]<0
                or (key not in SAME_DAY and max(ages[key],receive_ages[key])>policy.max_age_seconds)):
            stale.append(key)
        if lags[key]>policy.max_recorded_lag_seconds or -lags[key]>policy.max_clock_skew_seconds:
            lagging.append(key)
    reasons=[]
    if connection_state!="connected":reasons.append("CONNECTION_NOT_ACTIVE")
    if state is None:reasons.append("NO_BASELINE")
    if missing:reasons.append("MISSING_FIELDS")
    if invalid:reasons.append("INVALID_VALUES")
    if stale:reasons.append("STALE_FIELDS")
    if time_missing:reasons.append("FIELD_TIME_MISSING")
    if lagging:reasons.append("EXCESS_RECORDED_LAG")
    if session!="LO":reasons.append("SESSION_NOT_LO")
    if policy.require_symbol_status and payload.get("tradingStatus")!="NORMAL":reasons.append("STATUS_NOT_NORMAL")
    if counter_issues:reasons.append("COUNTER_DECREASE")
    warnings=[]
    if session_basis=="schedule":warnings.append("SESSION_FROM_SCHEDULE")
    if not policy.require_symbol_status:warnings.append("SYMBOL_STATUS_NOT_PROVIDED")
    if state and state.get("metadata",{}).get("derived_fields",{}).get("totalTradingValue"):
        warnings.append("TOTAL_VALUE_DERIVED")
    if state and state.get("metadata",{}).get("foreign_value_estimated"):
        warnings.append("FOREIGN_VALUE_ESTIMATED")
    if clock_skew:warnings.append("SOURCE_CLOCK_AHEAD_OF_RECEIVE")
    return {**member,"as_of":cutoff.isoformat(),"payload":payload,
        "field_updated_at":state.get("field_updated_at",{}) if state else {},
        "field_received_at":state.get("field_received_at",{}) if state else {},
        "field_issues":field_issues,"field_message_type":state.get("field_message_type",{}) if state else {},
        "missing_fields":missing,"invalid_fields":invalid,"stale_fields":stale,"time_missing_fields":time_missing,
        "lagging_fields":lagging,"source_age_seconds":ages,"receive_age_seconds":receive_ages,"recorded_lag_seconds":lags,
        "counter_issues":sorted(counter_issues),"reasons":reasons,"warnings":warnings,
        "fields_complete":not missing,"data_usable":not reasons,"ranking_ready":False,
        "needed_fields":list(needed),"trading_session":session,"session_basis":session_basis,
        "metadata":state.get("metadata",{}) if state else {}}


def group_coverage(rows):
    result={}
    for group in sorted({r["index_group"] for r in rows}):
        members=[row for row in rows if row["index_group"]==group]
        count=len(members)
        fields={}
        needed=[key for key in NEEDED if all(key in r.get("needed_fields",NEEDED) for r in members)]
        for key in needed:
            present=sum(key not in r["missing_fields"] for r in members)
            fresh=sum(all(key not in r[k] for k in ("missing_fields","invalid_fields","stale_fields","time_missing_fields","lagging_fields")) for r in members)
            fields[key]={"present":present,"fresh_valid":fresh,"total":count,"fresh_valid_percent":100*fresh/count}
        usable=sum(r["data_usable"] for r in members)
        result[group]={"members":count,"fields_complete":sum(r["fields_complete"] for r in members),
            "data_usable":usable,"data_usable_percent":100*usable/count,"fields":fields}
    return result
