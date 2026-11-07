from copy import deepcopy
import json
import pytest
from src.ssi_api.decoder import DecodeError, decode_fcdata
from src.ssi_api.decode_sample import sample_messages

RECEIVED="2026-11-04T10:00:01+07:00"


def decode(message,**kwargs):
    return decode_fcdata(message,received_at=RECEIVED,source="synthetic",**kwargs)


def event(kind="X-TRADE",**fields):
    return {"DataType":kind,"Content":{"Symbol":"DEMO01","TradingDate":"04/11/2026","Time":"10:00:00",
        "Exchange":"HOSE",**fields}}


@pytest.mark.parametrize("encoding",["object","json","bytes","bare","content_json"])
def test_supported_envelope_forms_are_equivalent(encoding):
    message=event(LastPrice="20000",LastVol=100,TotalVol=5000)
    expected=decode(message)
    if encoding=="json":message=json.dumps(message)
    elif encoding=="bytes":message=json.dumps(message).encode()
    elif encoding=="bare":message={**message["Content"],"RType":"X-TRADE"}
    elif encoding=="content_json":message["Content"]=json.dumps(message["Content"])
    assert decode(message)==expected


@pytest.mark.parametrize("item",sample_messages(),ids=["F","Quote","Trade","Room","B","X"])
def test_six_documented_message_types_keep_provenance(item):
    result=decode(item)
    assert result["source"]=="synthetic" and result["profile"]=="fcdata_v2"
    assert result["source_at"]=="2026-11-04T10:00:00+07:00"
    assert result["update_mode"]=="patch" and result["received_at"]==RECEIVED


def test_patch_does_not_fill_missing_keys_and_null_clears_only_present_field():
    missing=decode(event(LastPrice=100))
    null=decode(event(LastPrice=100,TotalVol=None))
    assert "totalTradingVolume" not in missing["payload"]
    assert null["payload"]["totalTradingVolume"] is None
    assert "totalTradingVolume" in null["present_fields"]
    assert "openPrice" not in null["payload"]


def test_trade_deltas_and_cumulative_values_are_separate():
    row=decode(event(LastVol=100,TotalVol=5000,TotalVal=100000,LastPrice=20000))["payload"]
    assert row["lastTradeVolume"]==100 and row["totalTradingVolume"]==5000 and row["totalTradingValue"]==100000
    only_last=decode(event(LastVol=100))["payload"]
    assert "totalTradingVolume" not in only_last


def test_quote_keeps_three_levels_auction_and_zero_volumes():
    row=decode(event("X-QUOTE",BidPrice1="ATO",AskPrice1="ATC",BidVol1=0,BidPrice4=20000))["payload"]
    assert row["bidPrice1"]=="ATO" and row["askPrice1"]=="ATC" and row["bidVol1"]==0
    assert "bidPrice4" not in row and "bidPrice2" not in row


def test_snapshot_does_not_replace_last_trade_with_close():
    row=decode(event("X",LastPrice=20000,Close=19000))["payload"]
    assert row["closePrice"]==20000 and row["ohlcClosePrice"]==19000
    assert "closePrice" not in decode(event("X",Close=19000))["payload"]


def test_b_value_is_never_cumulative_turnover():
    row=decode(event("B",Open=100,Close=110,Volume=50,Value=0))
    assert "totalTradingValue" not in row["payload"] and "totalTradingVolume" not in row["payload"]
    assert row["payload"]["lastTradeVolume"]==50
    assert any(i["code"]=="B_VALUE_NOT_CUMULATIVE" for i in row["issues"])


def test_room_aliases_agree_after_conversion_and_estimate_is_explicit():
    row=decode(event("R",FBuyVal="100",BuyVal=100,FSellVal=200,BuyVol=5,SellVol=10))
    assert row["payload"]["foreignBuyValue"]==100 and row["payload"]["foreignSellValue"]==200
    assert row["metadata"]["foreign_value_estimated"] is True
    assert "foreignBuyValue" not in row["metadata"]["counter_fields"]
    assert row["payload"]["foreignBuyValue"]-row["payload"]["foreignSellValue"]==-100
    with pytest.raises(DecodeError,match="ALIAS_CONFLICT"):
        decode(event("R",FBuyVal=101,BuyVal=100))
    hnx=decode(event("R",Exchange="HNX",BuyVal=100))
    assert hnx["metadata"]["foreign_value_estimated"] is None  # not documented does not mean exact


@pytest.mark.parametrize("value",[True,{},[],"bad","",-1,"NaN","inf",float("nan"),float("inf")])
def test_bad_numbers_are_missing_with_safe_issue(value):
    row=decode(event(LastPrice=value))
    assert row["payload"]["closePrice"] is None
    assert {"code":"INVALID_NUMBER","field":"closePrice"} in row["issues"]


@pytest.mark.parametrize("status,expected",[("N","NORMAL"),("H","HALT"),("?",None),(None,None)])
def test_status_mapping_does_not_assume_normal(status,expected):
    assert decode(event("F",TradingStatus=status))["payload"]["tradingStatus"]==expected


def test_session_unknown_is_not_assumed_lo_and_market_is_not_inferred():
    row=decode(event("F",TradingSession="UNKNOWN",Exchange=None))
    assert row["payload"]["tradingSession"] is None and row["payload"]["marketCode"] is None


@pytest.mark.parametrize("date,time",[("04112026","100000"),("2026-11-04","10:00:00"),("04/11/2026","10:00:00")])
def test_source_date_and_time_formats(date,time):
    row=decode(event(TradingDate=date,Time=time))
    assert row["source_at"]=="2026-11-04T10:00:00+07:00"


@pytest.mark.parametrize("changes",[{"TradingDate":None},{"TradingDate":"31/02/2026"},{"Time":"25:00:00"},
    {"TradingDate":"04/11/2026","Time":"2026-11-05T10:00:00+07:00"}])
def test_invalid_source_time_is_not_replaced_with_received_time(changes):
    row=decode(event(**changes))
    assert row["source_at"] is None
    assert any(i["code"]=="SOURCE_TIME_UNAVAILABLE" for i in row["issues"])


def test_missing_day_not_inferred_from_receive_date():
    message=event("B",Close=100,TradingTime="10:00:00")
    del message["Content"]["TradingDate"]
    del message["Content"]["Time"]
    row=decode(message)
    assert row["source_at"] is None and "tradingDate" not in row["payload"]


@pytest.mark.parametrize("message",["bad json",[],None,{"Content":[]},{"DataType":"MI","Content":{"Symbol":"VN30"}},
    {"DataType":"F","Content":{"Symbol":"?"}},{"DataType":"F","Content":{"Symbol":"DEMO01","RType":"R"}},
    {"DataType":"F","Content":{"Symbol":"DEMO01","MarketId":"HNX","Exchange":"HOSE"}},
    '{"DataType":"F","DataType":"R","Symbol":"A"}',
    {"DataType":"F","Content":{"Symbol":"A","symbol":"B"}}])
def test_structural_or_conflicting_messages_fail_closed(message):
    with pytest.raises(DecodeError):decode(message)


def test_unsupported_profile_and_naive_receive_clock_are_rejected():
    with pytest.raises(DecodeError):decode(event(),profile="fastconnect_v3")
    with pytest.raises(DecodeError):decode_fcdata(event(),received_at="2026-11-04T10:00:00")


def test_no_state_mutation_no_unmapped_secret_values_in_output():
    message=event(LastPrice=100,accessToken="PRIVATE_SENTINEL",unexpected="PRIVATE_SENTINEL")
    before=deepcopy(message)
    result=decode(message)
    assert message==before and "PRIVATE_SENTINEL" not in json.dumps(result)
    result["payload"]["closePrice"]=500
    assert decode(message)["payload"]["closePrice"]==100
