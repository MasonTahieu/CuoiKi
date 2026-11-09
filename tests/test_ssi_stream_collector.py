from copy import deepcopy
from datetime import date
import json
import pytest

from src.ssi_api.decoder import decode_fcdata
from src.ssi_api.stream_collector import (Frame, PatchState, StreamDisconnected, StreamAuthFailed,
    collect_stream, subscription_plan, validate_members)
from src.ssi_api.fake_stream import FakeClock, FakeFactory
from src.data.store import EventStore, read_events

MEMBERS=[{"symbol":"DEMO01","marketCode":"HOSE","index_group":"VN30"},
         {"symbol":"DEMO02","marketCode":"HOSE","index_group":"VN30"}]


def frame(kind="X",symbol="DEMO01",at="10:00:00",received="10:00:01",**fields):
    return Frame({"DataType":kind,"Content":{"Symbol":symbol,"Exchange":"HOSE",
        "TradingDate":"04/11/2026","Time":at,**fields}},"2026-11-04T"+received+"+07:00")


def decoded(item):
    return decode_fcdata(item.raw,received_at=item.received_at,source="synthetic")


def baseline(symbol="DEMO01",at="10:00:00",received="10:00:01"):
    prices={f"{side}{field}{i}": (20000+(-1 if side=="Bid" else 1)*i*50 if field=="Price" else 1000*i)
        for side in ("Bid","Ask") for field in ("Price","Vol") for i in (1,2,3)}
    return [frame(symbol=symbol,at=at,received=received,Open=19900,LastPrice=20000,
        TotalVal=2000000000,TotalVol=100000,TradingSession="LO",TradingStatus="N",**prices),
        frame("R",symbol,at,received,BuyVal=40000000,SellVal=20000000,BuyVol=2000,SellVol=1000)]


def run(scripts,**options):
    clock=FakeClock()
    factory=FakeFactory(MEMBERS,scripts,clock)
    journal=[]
    report=collect_stream(factory,lambda **event:journal.append(event),seconds=options.pop("seconds",30),
        clock=clock.monotonic,sleep=clock.sleep,wall_now=clock.wall_now,**options)
    return report,factory,journal,clock


def test_incremental_merge_keeps_field_clocks_and_null_invalidates():
    merge=PatchState(MEMBERS,date(2026,11,4))
    for item in baseline():state,_=merge.apply(decoded(item))
    assert state["fields_complete"] and not state["ranking_ready"]
    update=frame("X-QUOTE",at="10:00:02",received="10:00:03",BidPrice1=19975,BidVol1=None)
    state,reason=merge.apply(decoded(update))
    assert reason=="merged" and state["payload"]["bidVol1"] is None
    assert "bidVol1" in state["missing_fields"]
    assert state["payload"]["askPrice1"]==20050
    assert state["field_updated_at"]["foreignBuyValue"]=="2026-11-04T10:00:00+07:00"
    assert state["field_updated_at"]["bidPrice1"]=="2026-11-04T10:00:02+07:00"
    assert state["metadata"]["foreign_value_estimated"] is True


def test_old_field_cannot_replace_new_but_can_supply_missing_field():
    merge=PatchState(MEMBERS,date(2026,11,4))
    merge.apply(decoded(frame("X-TRADE",at="10:00:05",received="10:00:06",LastPrice=21000)))
    state,_=merge.apply(decoded(frame("X",at="10:00:01",received="10:00:07",LastPrice=20000,Open=19900)))
    assert state["payload"]["closePrice"]==21000 and state["payload"]["openPrice"]==19900
    assert state["field_updated_at"]["closePrice"].endswith("10:00:05+07:00")


def test_exact_duplicate_does_not_refresh_clock_but_newer_same_value_does():
    merge=PatchState(MEMBERS,date(2026,11,4))
    item=decoded(frame("X-TRADE",LastPrice=20000))
    merge.apply(item)
    item["received_at"]="2026-11-04T10:00:05+07:00"
    assert merge.apply(item)==(None,"duplicate")
    state,_=merge.apply(decoded(frame("X-TRADE",at="10:00:06",received="10:00:07",LastPrice=20000)))
    assert state["field_updated_at"]["closePrice"].endswith("10:00:06+07:00")


def test_status_is_per_symbol_and_equal_timestamp_uses_arrival_order():
    merge=PatchState(MEMBERS,date(2026,11,4))
    for symbol in ("DEMO01","DEMO02"):
        merge.apply(decoded(frame("F",symbol,TradingStatus="N",TradingSession="LO")))
    merge.apply(decoded(frame("F",TradingStatus="H")))
    assert merge.states["DEMO01"]["payload"]["tradingStatus"]=="HALT"
    assert merge.states["DEMO02"]["payload"]["tradingStatus"]=="NORMAL"


@pytest.mark.parametrize("change,reason",[("market","market_mismatch"),("symbol","outside_universe"),
    ("time","source_time_missing"),("day","wrong_day"),("future","source_time_in_future")])
def test_invalid_patch_not_merged(change,reason):
    item=decoded(frame("X-TRADE",LastPrice=20000))
    if change=="market":item["payload"]["marketCode"]="HNX"
    elif change=="symbol":item["payload"]["symbol"]="OUTSIDE"
    elif change=="time":item["source_at"]=None
    elif change=="day":item["source_at"]="2026-11-03T10:00:00+07:00"
    elif change=="future":item["source_at"]="2026-11-04T10:00:20+07:00"
    assert PatchState(MEMBERS,date(2026,11,4)).apply(item)==(None,reason)


def test_estimated_foreign_value_can_fall_without_inventing_rollback():
    merge=PatchState(MEMBERS,date(2026,11,4))
    merge.apply(decoded(frame("R",BuyVal=1000)))
    state,_=merge.apply(decoded(frame("R",at="10:00:01",received="10:00:02",BuyVal=900)))
    assert state["payload"]["foreignBuyValue"]==900
    assert state["metadata"]["foreign_value_estimated"] is True


def test_reconnect_discards_baseline_and_resubscribes():
    report,factory,journal,_=run([baseline()+[StreamDisconnected()],
        [frame("X-TRADE",at="10:00:03",received="10:00:04",LastPrice=20100)]],seconds=6)
    state=report["states"]["DEMO01"]
    assert "openPrice" not in state["payload"] and not state["fields_complete"]
    assert report["counters"]["reconnects"]==1
    assert factory.bootstrap_calls==2 and len(factory.sessions)==2
    assert all(s.closed and s.channels==subscription_plan(MEMBERS) for s in factory.sessions)
    assert not any(e["channel"]=="marketSession" for e in journal)
    assert report["source"]=="synthetic" and report["network_called"] is False


def test_reconnect_rebuilds_baseline_only_from_new_epoch():
    report,_,journal,_=run([baseline()+[StreamDisconnected()],baseline(at="10:00:03",received="10:00:04")],seconds=6)
    assert report["states"]["DEMO01"]["fields_complete"]
    latest=[e["payload"] for e in journal if e["channel"]=="ssiMerged"][-1]
    assert latest["connection_epoch"]==2
    assert all(t.endswith("10:00:03+07:00") for t in latest["field_updated_at"].values())


def test_auth_failure_stops_without_reconnect_and_does_not_leak_message():
    report,factory,journal,_=run([[StreamAuthFailed("PRIVATE_SENTINEL")]])
    assert report["stop_reason"]=="auth_failed" and report["states"]=={}
    assert report["counters"]["reconnects"]==0 and factory.sessions[0].closed
    assert "PRIVATE_SENTINEL" not in json.dumps(journal)


def test_reconnect_limit_and_backoff_are_bounded():
    report,factory,_,clock=run([[StreamDisconnected()]]*4,max_reconnects=3)
    assert report["stop_reason"]=="reconnect_limit"
    assert len(factory.sessions)==4 and clock.value==7
    assert report["states"]=={}


def test_wait_between_failures_is_capped():
    report,factory,_,clock=run([[StreamDisconnected()]]*8,max_reconnects=7,seconds=1000)
    assert report["stop_reason"]=="reconnect_limit" and clock.value==1+2+4+8+16+30+30


def test_routine_token_cycles_do_not_add_up_to_a_failure():
    # Each connection delivers data for over a minute, then the SDK reopens it for a new token.
    def cycle(first,last):
        return [frame("X-TRADE",at=first,received=first,LastPrice=20000),
                frame("X-TRADE",at=last,received=last,LastPrice=20100),StreamDisconnected()]
    report,factory,_,clock=run([cycle("10:00:01","10:01:10"),cycle("10:01:12","10:02:20"),cycle("10:02:22","10:03:30")],
                               max_reconnects=1,seconds=300,idle_seconds=100)
    assert report["counters"]["reconnects"]==3 and len(factory.sessions)==4
    assert report["stop_reason"]=="reconnect_limit"  # a dead connection right after still counts
    assert clock.value==211  # the last frame at 210 s, then a one-second wait each time, not 1, 2, 4


def test_data_for_too_short_a_time_does_not_clear_failures():
    quick=[frame("X-TRADE",at="10:00:01",received="10:00:01",LastPrice=20000),StreamDisconnected()]
    report,factory,_,_=run([quick,[StreamDisconnected()],[StreamDisconnected()]],max_reconnects=2,seconds=300)
    assert report["stop_reason"]=="reconnect_limit" and len(factory.sessions)==3


def test_idle_timeout_reconnects_without_real_sleep():
    report,factory,_,clock=run([[],[]],idle_seconds=2,max_reconnects=1)
    assert report["stop_reason"]=="reconnect_limit" and len(factory.sessions)==2
    assert clock.value<10


def test_message_and_duration_limits_stop_and_close():
    report,factory,_,_=run([baseline()*5],max_messages=2)
    assert report["stop_reason"]=="message_limit" and report["counters"]["received"]==2
    assert factory.sessions[0].closed
    report,factory,_,clock=run([[]],seconds=1,idle_seconds=15)
    assert report["stop_reason"]=="duration_limit" and clock.value==1


def test_bad_frame_is_recorded_safely_and_next_message_still_processed():
    bad=Frame('{"PRIVATE_SENTINEL":bad}',"2026-11-04T10:00:00+07:00")
    good=frame("X-TRADE",LastPrice=20000,accessToken="PRIVATE_SENTINEL",unknown="PRIVATE_SENTINEL")
    report,_,journal,_=run([[bad,good]],max_messages=2)
    assert report["counters"]["decode_errors"]==1 and report["counters"]["merged"]==1
    assert "PRIVATE_SENTINEL" not in json.dumps(journal)
    raw=next(e["payload"] for e in journal if e["channel"]=="ssiRaw")
    assert raw["message"]["Content"]["LastPrice"]==20000


def test_disconnected_state_is_not_returned_as_live_baseline():
    report,_,_,_=run([baseline()+[StreamDisconnected()]],max_reconnects=0)
    assert report["states"]=={}


@pytest.mark.parametrize("members",[[],MEMBERS+[MEMBERS[0]], [{"symbol":"A","index_group":"HNX30","marketCode":"HOSE"}]])
def test_invalid_bootstrap_fails_before_creating_session(members):
    with pytest.raises(ValueError):validate_members(members)


def test_sink_error_closes_transport_and_caller_snapshot_cannot_mutate_state():
    clock=FakeClock()
    factory=FakeFactory(MEMBERS,[baseline()],clock)
    def sink(**event):
        if event["channel"]=="ssiMerged":raise OSError("sink unavailable")
    with pytest.raises(OSError):
        collect_stream(factory,sink,clock=clock.monotonic,sleep=clock.sleep,wall_now=clock.wall_now)
    assert factory.sessions[0].closed
    merge=PatchState(MEMBERS,date(2026,11,4))
    state,_=merge.apply(decoded(frame("X-TRADE",LastPrice=100)))
    state["payload"]["closePrice"]=1
    assert merge.states["DEMO01"]["payload"]["closePrice"]==100


def test_sqlite_sink_keeps_decoder_field_times_and_source(tmp_path):
    clock=FakeClock()
    store=EventStore(tmp_path/"stream.sqlite")
    factory=FakeFactory(MEMBERS,[baseline()],clock)
    try:
        report=collect_stream(factory,store.append,seconds=2,clock=clock.monotonic,sleep=clock.sleep,wall_now=clock.wall_now)
    finally:store.close()
    events=read_events(tmp_path/"stream.sqlite",report["run"])
    assert all(e["source"]=="synthetic" for e in events)
    assert next(e for e in events if e["channel"]=="ssiDecoded")["payload"]["source_at"]
    assert next(e for e in events if e["channel"]=="ssiMerged")["payload"]["field_updated_at"]


def test_bad_numeric_values_do_not_crash_sqlite_raw_sink(tmp_path):
    clock=FakeClock()
    store=EventStore(tmp_path/"bad.sqlite")
    items=[frame("X-TRADE",LastPrice=float("nan")),
           frame("X-TRADE",at="10:00:02",received="10:00:03",LastPrice={"secret":"PRIVATE_SENTINEL"})]
    try:
        report=collect_stream(FakeFactory(MEMBERS,[items],clock),store.append,seconds=4,
            clock=clock.monotonic,sleep=clock.sleep,wall_now=clock.wall_now)
    finally:store.close()
    events=read_events(tmp_path/"bad.sqlite",report["run"])
    assert report["counters"]["decoded"]==2
    assert "PRIVATE_SENTINEL" not in json.dumps(events,allow_nan=False)
    assert report["states"]["DEMO01"]["payload"]["closePrice"] is None


def test_bootstrap_and_subscribe_failures_close_and_retry(monkeypatch):
    clock=FakeClock()
    factory=FakeFactory(MEMBERS,[[],baseline(received="10:00:03")],clock)
    create=factory.create
    def failing_first():
        session=create()
        if len(factory.sessions)==1:
            def fail(channels):raise StreamDisconnected()
            session.subscribe=fail
        return session
    monkeypatch.setattr(factory,"create",failing_first)
    report=collect_stream(factory,lambda **e:None,seconds=5,clock=clock.monotonic,sleep=clock.sleep,wall_now=clock.wall_now)
    assert factory.bootstrap_calls==2 and all(s.closed for s in factory.sessions)
    assert report["states"]["DEMO01"]["fields_complete"]


def test_duplicate_memory_is_bounded():
    merge=PatchState(MEMBERS,date(2026,11,4),dedup_limit=2)
    for i in range(5):
        merge.apply(decoded(frame("X-TRADE",at=f"10:00:0{i}",received=f"10:00:0{i+1}",LastPrice=20000+i)))
    assert len(merge.seen)==2


def test_day_rollover_requires_rebootstrap_and_cannot_keep_old_fields():
    clock=FakeClock("2026-11-04T23:59:58+07:00")
    next_day=Frame({"DataType":"X-TRADE","Content":{"Symbol":"DEMO01","Exchange":"HOSE",
        "TradingDate":"05/11/2026","Time":"00:00:00","LastPrice":20000}},"2026-11-05T00:00:00+07:00")
    factory=FakeFactory(MEMBERS,[[next_day],[Frame(next_day.raw,"2026-11-05T00:00:02+07:00")]],clock)
    report=collect_stream(factory,lambda **e:None,seconds=6,clock=clock.monotonic,sleep=clock.sleep,wall_now=clock.wall_now)
    assert factory.bootstrap_calls==2
    assert report["states"]["DEMO01"]["payload"]["tradingDate"]=="05/11/2026"
    assert report["states"]["DEMO01"]["fields_complete"] is False
