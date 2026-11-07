import hashlib
import json
import sqlite3
import pytest

from src.data.store import EventStore,read_events,timestamp
from src.data.ssi_journal import SSIJournal,JournalError,BufferedSink
from src.data.ssi_quality import QualityPolicy
from src.ssi_api.replay import replay,export_report
from src.ssi_api.collect_sample import scenario
from src.ssi_api.fake_stream import FakeFactory,FakeClock
from src.ssi_api.stream_collector import Frame,StreamDisconnected,StreamAuthFailed,collect_stream


def save_scenario(path,scripts=None,members=None,seconds=30,max_messages=15,max_reconnects=3):
    defaults,script=scenario()
    clock=FakeClock()
    store=EventStore(path)
    sink=BufferedSink(store,8)
    try:
        report=collect_stream(FakeFactory(members or defaults,scripts or script,clock),sink,
            seconds=seconds,max_messages=max_messages,max_reconnects=max_reconnects,
            clock=clock.monotonic,sleep=clock.sleep,wall_now=clock.wall_now)
        sink.flush()
    finally:store.close()
    return report


@pytest.fixture
def journal(tmp_path):
    path=tmp_path/"collector.sqlite"
    report=save_scenario(path)
    return path,report


def at(path,run,second,**kwargs):
    return replay(path,run,as_of=f"2026-11-04T10:00:{second}+07:00",**kwargs)


def symbol(report,name="DEMO01"):
    return next(row for row in report["rows"] if row["symbol"]==name)


def frame(kind="X-TRADE",second=1,received=2,**fields):
    return Frame({"DataType":kind,"Content":{"Symbol":"DEMO01","Exchange":"HOSE",
        "TradingDate":"04/11/2026","Time":f"10:00:{second:02d}",**fields}},
        f"2026-11-04T10:00:{received:02d}+07:00")


def test_replay_from_decoded_is_deterministic_and_matches_collector_values(journal):
    path,collected=journal
    first=replay(path,collected["run"])
    assert first==replay(path,collected["run"])
    for name,state in collected["states"].items():
        row=symbol(first,name)
        assert row["payload"]==state["payload"]
        assert row["field_updated_at"]==state["field_updated_at"]
    assert first["last_recorded_connection_state"]=="stopped"
    assert all(not r["data_usable"] for r in first["rows"])
    assert first["ranking_ready"] is False


def test_asof_does_not_use_future_snapshot_and_same_second_cursor_is_precise(journal):
    path,collected=journal
    report=at(path,collected["run"],"01")
    assert symbol(report)["payload"]["closePrice"]==20000
    assert symbol(report)["data_usable"]
    with SSIJournal(path) as reader:
        decoded=next(e for e in reader.events(collected["run"]) if e["channel"]=="ssiDecoded")
    partial=replay(path,collected["run"],through_event_id=decoded["event_id"])
    assert "foreignBuyValue" in symbol(partial)["missing_fields"]
    assert not symbol(partial)["fields_complete"]


def test_no_data_before_bootstrap_and_at_new_day(journal):
    path,collected=journal
    early=replay(path,collected["run"],"2026-11-04T09:59:59+07:00")
    assert early["rows"]==[] and early["statistics"]=={}
    tomorrow=replay(path,collected["run"],"2026-11-05T10:00:00+07:00")
    assert tomorrow["rows"]==[] and tomorrow["group_coverage"]=={}


def test_gap_clears_values_and_recovery_does_not_forward_fill(journal):
    path,collected=journal
    gap=at(path,collected["run"],"06.500000")
    assert gap["last_recorded_connection_state"]=="disconnected"
    assert symbol(gap)["payload"]=={} and "NO_BASELINE" in symbol(gap)["reasons"]
    assert gap["gaps"]==[{"kind":"disconnected","start":"2026-11-04T10:00:06+07:00",
        "end":"2026-11-04T10:00:06.500000+07:00","seconds":.5,"open_ended":True}]
    recovery=at(path,collected["run"],"09")
    assert "foreignBuyValue" in symbol(recovery)["missing_fields"]
    assert "openPrice" in symbol(recovery)["missing_fields"]
    ready=at(path,collected["run"],"11")
    assert symbol(ready)["data_usable"]
    assert ready["gaps"][0]["seconds"]==1
    assert ready["gaps"][0]["open_ended"] is False


def test_field_missing_and_group_coverage_are_asof_specific(journal):
    path,collected=journal
    report=at(path,collected["run"],"03")
    assert symbol(report)["missing_fields"]==["bidVol1"]
    assert symbol(report,"HNDEMO01")["data_usable"]
    assert report["group_coverage"]["VN30"]["data_usable_percent"]==0
    assert report["group_coverage"]["HNX30"]["data_usable_percent"]==100
    assert report["group_coverage"]["VN30"]["fields"]["bidVol1"]["present"]==0


def test_status_is_per_symbol_and_full_fields_do_not_mean_usable(journal):
    path,collected=journal
    # End the replay just after F, before the stopped marker sharing the timestamp.
    with SSIJournal(path) as reader:
        marker=[e for e in reader.events(collected["run"]) if e["channel"]=="ssiDecoded"][-1]
    report=replay(path,collected["run"],through_event_id=marker["event_id"])
    halted=symbol(report,"HNDEMO01")
    assert halted["fields_complete"] and "STATUS_NOT_NORMAL" in halted["reasons"]
    assert symbol(report)["data_usable"]
    assert report["group_coverage"]["HNX30"]["fields_complete"]==1


def test_stale_foreign_fields_are_not_refreshed_by_new_quote(tmp_path):
    members,scripts=scenario()
    # Quotes keep the stream active without refreshing the foreign-flow fields.
    quotes=[Frame({"DataType":"X-QUOTE","Content":{"Symbol":"DEMO01","Exchange":"HOSE",
        "TradingDate":"04/11/2026","Time":f"10:{second//60:02d}:{(second-1)%60:02d}","BidPrice1":19990}},
        f"2026-11-04T10:{second//60:02d}:{second%60:02d}+07:00") for second in (10,20,30,40,50,63)]
    path=tmp_path/"stale.sqlite"
    collected=save_scenario(path,[scripts[0][:2]+quotes],seconds=65,max_messages=100,max_reconnects=0)
    result=replay(path,collected["run"],"2026-11-04T10:01:03+07:00")
    row=symbol(result)
    assert result["last_recorded_connection_state"]=="connected"
    assert "foreignBuyValue" in row["stale_fields"] and "bidPrice1" not in row["stale_fields"]
    assert "openPrice" not in row["stale_fields"]
    assert row["source_age_seconds"]["foreignBuyValue"]==63
    assert row["recorded_lag_seconds"]["bidPrice1"]==1


def test_source_after_cutoff_never_appears_early(tmp_path):
    path=tmp_path/"future.sqlite"
    collected=save_scenario(path,[[frame(second=5,received=1,LastPrice=21000)]],seconds=2,max_messages=1)
    report=at(path,collected["run"],"01")
    assert symbol(report)["payload"]=={}
    assert report["statistics"]["source_after_cutoff"]==1


def test_counter_decrease_blocks_but_foreign_estimate_decrease_does_not(tmp_path):
    _,scripts=scenario()
    path=tmp_path/"counters.sqlite"
    items=scripts[0][:2]+[
        frame(second=1,received=2,LastPrice=15000,TotalVol=100100,TotalVal=2001500000),
        frame("R",2,3,BuyVal=30015000,SellVal=15000000,BuyVol=2001,SellVol=1000),
        frame(second=3,received=4,TotalVol=1),
        frame("R",4,5,BuyVol=2000),
    ]
    report=save_scenario(path,[items],seconds=6,max_messages=100)
    before=symbol(at(path,report["run"],"01"))
    after_price=symbol(at(path,report["run"],"03"))
    assert after_price["payload"]["closePrice"] < before["payload"]["closePrice"]
    assert after_price["payload"]["foreignBuyValue"] < before["payload"]["foreignBuyValue"]
    assert after_price["payload"]["foreignBuyVolume"] > before["payload"]["foreignBuyVolume"]
    assert after_price["data_usable"]
    assert "FOREIGN_VALUE_ESTIMATED" in after_price["warnings"]
    after=at(path,report["run"],"04")
    assert symbol(after)["counter_issues"]==["totalTradingVolume"]
    assert "COUNTER_DECREASE" in symbol(after)["reasons"]
    assert symbol(at(path,report["run"],"05"))["counter_issues"]==["foreignBuyVolume","totalTradingVolume"]


def test_recorded_lag_and_clock_skew_have_separate_meaning(tmp_path):
    path=tmp_path/"lags.sqlite"
    collected=save_scenario(path,[[frame(second=0,received=12,LastPrice=100)]],seconds=14,max_messages=100)
    row=symbol(replay(path,collected["run"],"2026-11-04T10:00:13+07:00"))
    assert row["recorded_lag_seconds"]["closePrice"]==12
    assert "closePrice" in row["lagging_fields"]
    assert "EXCESS_RECORDED_LAG" in row["reasons"]


def test_duplicate_and_late_messages_counted_once_from_decoded(journal):
    path,collected=journal
    stats=replay(path,collected["run"])["statistics"]
    assert stats["decoded"]==14 and stats["merged"]==11 and stats["duplicate"]==1
    assert stats["decode_errors"]==1 and stats["late_messages"]==1 and stats["late_fields_ignored"]==4


def test_poisoned_cached_snapshot_never_controls_replay(journal):
    path,collected=journal
    store=EventStore(path)
    store.append("synthetic",collected["run"],"2026-11-04T10:00:02+07:00","ssiMerged",{"payload":{"closePrice":9999999}})
    store.close()
    assert symbol(at(path,collected["run"],"02"))["payload"]["closePrice"]==20000


def test_reader_does_not_create_file_and_refuses_wrong_run(tmp_path,journal):
    missing=tmp_path/"missing.sqlite"
    with pytest.raises(JournalError):
        with SSIJournal(missing):pass
    assert not missing.exists()
    path,collected=journal
    with pytest.raises(JournalError):replay(path,"does-not-exist")
    with pytest.raises(JournalError):replay(path,collected["run"],through_event_id=999999)


def test_run_sources_cannot_be_mixed_and_neo_not_accepted(journal):
    path,collected=journal
    store=EventStore(path)
    store.append("ssi",collected["run"],"2026-11-04T10:00:01+07:00","connection",{"state":"connected"})
    store.close()
    with pytest.raises(JournalError):replay(path,collected["run"])


def test_multiple_runs_stay_separate_and_default_uses_latest_collector(journal):
    path,first=journal
    second=save_scenario(path)
    assert first["run"]!=second["run"]
    with SSIJournal(path) as reader:
        runs=reader.runs()
    assert [r["run"] for r in runs]==[second["run"],first["run"]]
    assert replay(path)["run"]==second["run"]
    assert replay(path,first["run"])["statistics"]["decoded"]==14


def test_streaming_read_snapshot_is_consistent_while_writer_appends(journal):
    path,collected=journal
    with SSIJournal(path) as reader:
        info=reader.describe(collected["run"])
        store=EventStore(path)
        store.append("synthetic",collected["run"],"2026-11-04T10:00:20+07:00","connection",{"state":"stopped","connection_epoch":2})
        store.close()
        ids=[e["event_id"] for e in reader.events(collected["run"],batch_size=2)]
        assert ids[-1]==info["last_event_id"]


def test_batch_atomicity_idempotence_and_boundary_flush(tmp_path):
    path=tmp_path/"batch.sqlite"
    store=EventStore(path)
    event=dict(source="synthetic",run="batch",received_at="2026-11-04T10:00:00+07:00",channel="ssiRaw",payload={"data":1})
    assert store.append_many([event,event])==1
    bad={**event,"received_at":"2026-11-04T10:00:01+07:00","payload":{"bad":float("nan")}}
    with pytest.raises(ValueError):store.append_many([{**event,"payload":{"data":2}},bad])
    assert len(read_events(path,"batch"))==1
    sink=BufferedSink(store,batch_size=3)
    other={**event,"payload":{"data":3}}
    sink(**other)
    other["payload"]["data"]=999
    assert len(read_events(path,"batch"))==1
    sink(source="synthetic",run="batch",received_at=event["received_at"],channel="connection",payload={"state":"stopped"})
    rows=read_events(path,"batch")
    assert len(rows)==3 and rows[1]["payload"]["data"]==3 and not sink.pending
    store.close()


def test_buffer_keeps_pending_if_write_fails():
    class BrokenStore:
        def append_many(self,_):raise OSError("failed")
    sink=BufferedSink(BrokenStore(),1)
    with pytest.raises(OSError):sink(source="synthetic",run="x",received_at="x",channel="ssiRaw",payload={})
    assert len(sink.pending)==1


@pytest.mark.parametrize("kwargs",[{"max_age_seconds":-1},{"max_age_seconds":float("nan")},{"max_recorded_lag_seconds":True}])
def test_invalid_quality_policy_rejected(kwargs):
    with pytest.raises(ValueError):QualityPolicy(**kwargs)


def test_invalid_json_fails_without_partial_report(journal):
    path,collected=journal
    with sqlite3.connect(path) as db:
        db.execute("UPDATE events SET payload='invalid' WHERE id=(SELECT id FROM events WHERE channel='ssiDecoded' AND run=? LIMIT 1)",(collected["run"],))
    with pytest.raises(JournalError):replay(path,collected["run"])


@pytest.mark.parametrize("change",[{"source":"ssi"},{"message_type":"UNKNOWN"},{"received_at":"invalid"}])
def test_corrupt_decoded_contract_fails_cleanly(journal,change):
    path,collected=journal
    with sqlite3.connect(path) as db:
        ident,raw=db.execute("SELECT id,payload FROM events WHERE channel='ssiDecoded' AND run=? LIMIT 1",(collected["run"],)).fetchone()
        db.execute("UPDATE events SET payload=? WHERE id=?",(json.dumps({**json.loads(raw),**change}),ident))
    with pytest.raises(JournalError):replay(path,collected["run"])


@pytest.mark.parametrize("missing_field", ["source_at", "foreign_value_estimated"])
def test_missing_decoded_metadata_returns_a_journal_error(journal, missing_field):
    path, collected = journal
    with sqlite3.connect(path) as db:
        events = db.execute("SELECT id,payload FROM events WHERE channel='ssiDecoded' AND run=? ORDER BY id",
                            (collected["run"],))
        for event_id, raw in events:
            item = json.loads(raw)
            if item["message_type"] == "R":
                container = item if missing_field == "source_at" else item["metadata"]
                del container[missing_field]
                db.execute("UPDATE events SET payload=? WHERE id=?", (json.dumps(item), event_id))
                break
        else:
            pytest.fail("The replay fixture must include a decoded R message.")
    with pytest.raises(JournalError):
        replay(path, collected["run"])


def test_missing_source_time_after_baseline_is_rejected_not_reused(tmp_path):
    _,scripts=scenario()
    missing=frame(second=2,received=3,LastPrice=1)
    del missing.raw["Content"]["Time"]
    path=tmp_path/"missing-time.sqlite"
    collected=save_scenario(path,[[*scripts[0][:2],missing]],seconds=4,max_messages=100)
    result=at(path,collected["run"],"03")
    assert symbol(result)["payload"]["closePrice"]==20000
    assert result["statistics"]["source_time_missing"]==1


def test_invalid_number_is_distinct_from_plain_null_and_recovers(tmp_path):
    _,scripts=scenario()
    path=tmp_path/"invalid-field.sqlite"
    items=[*scripts[0][:2],frame(second=2,received=3,LastPrice="invalid"),frame(second=3,received=4,LastPrice=20100)]
    collected=save_scenario(path,[items],seconds=5,max_messages=100)
    bad=symbol(at(path,collected["run"],"03"))
    assert "closePrice" in bad["missing_fields"] and "closePrice" in bad["invalid_fields"]
    assert bad["field_issues"]["closePrice"]==["INVALID_NUMBER"]
    good=symbol(at(path,collected["run"],"04"))
    assert good["data_usable"] and good["field_issues"]["closePrice"]==[]


def test_export_includes_missing_required_fields_without_any_clock(journal,tmp_path):
    import csv
    path,collected=journal
    report=at(path,collected["run"],"09")
    folder=tmp_path/"partial"
    export_report(report,folder)
    with (folder/"field_quality.csv").open(encoding="utf-8-sig",newline="") as f:rows=list(csv.DictReader(f))
    missing=next(r for r in rows if r["symbol"]=="DEMO01" and r["field"]=="foreignBuyValue")
    assert missing["missing"]=="True" and missing["required"]=="True"
    assert missing["source_at"]==""


def test_auth_failure_is_visible_without_old_baseline(tmp_path):
    _,scripts=scenario()
    path=tmp_path/"auth-failed.sqlite"
    collected=save_scenario(path,[[*scripts[0][:2],StreamDisconnected()],[StreamAuthFailed()]],seconds=5,max_messages=100)
    result=replay(path,collected["run"])
    assert result["last_recorded_connection_state"]=="auth_failed"
    assert symbol(result)["payload"]=={}
    assert "NO_BASELINE" in symbol(result)["reasons"]


def test_connection_only_run_is_discoverable(tmp_path):
    path=tmp_path/"empty-run.sqlite"
    store=EventStore(path)
    store.append("synthetic","bootstrap-failed","2026-11-04T10:00:00+07:00","connection",{"state":"connecting","connection_epoch":1})
    store.close()
    report=replay(path)
    assert report["run"]=="bootstrap-failed" and report["rows"]==[]
    assert report["last_recorded_connection_state"]=="connecting"


def test_export_keeps_source_quality_policy_and_hashes(journal,tmp_path):
    path,collected=journal
    report=at(path,collected["run"],"13")
    folder=tmp_path/"export"
    export_report(report,folder)
    manifest=json.loads((folder/"manifest.json").read_text())
    assert manifest["source"]=="synthetic" and manifest["run"]==collected["run"]
    for name,digest in manifest["files"].items():
        assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest
    csv=(folder/"snapshot.csv").read_text(encoding="utf-8-sig")
    assert "synthetic" in csv and "FOREIGN_VALUE_ESTIMATED" in csv
    assert json.loads((folder/"quality.json").read_text())["ranking_ready"] is False
