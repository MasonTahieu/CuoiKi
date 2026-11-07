"""Stateless FCData v2 decoder. No network, merging, scoring or clock inference."""
import json
import math
import re
from datetime import datetime
from src.data.store import TZ, timestamp

SUPPORTED = {"F", "X", "X-QUOTE", "X-TRADE", "R", "B"}
SESSIONS = {"LO", "ATO", "ATC", "PT", "C", "BREAK", "HALT"}


class DecodeError(ValueError):
    """Safe diagnostic: never includes the original body or values."""


def _unique(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise DecodeError("DUPLICATE_JSON_KEY: tên trường JSON bị lặp.")
        obj[key] = value
    return obj


def _object(value):
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeError:
            raise DecodeError("INVALID_UTF8: dữ liệu không phải UTF-8.") from None
    if isinstance(value, str):
        try:
            value = json.loads(value, object_pairs_hook=_unique,
                parse_constant=lambda _: (_ for _ in ()).throw(DecodeError("INVALID_JSON_NUMBER")))
        except (ValueError, RecursionError):
            raise DecodeError("INVALID_JSON: không giải mã được object JSON.") from None
    if not isinstance(value, dict) or not all(isinstance(k,str) for k in value):
        raise DecodeError("OBJECT_REQUIRED: cần object, không phải danh sách hoặc giá trị đơn.")
    return value


def _index(obj):
    result = {}
    for key,value in obj.items():
        lowered = key.lower()
        if lowered in result:
            raise DecodeError("DUPLICATE_FIELD: tên trường chỉ khác chữ hoa/thường.")
        result[lowered] = value
    return result


def _date(value):
    for fmt in ("%d/%m/%Y", "%d%m%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value),fmt).date()
        except ValueError:
            pass
    raise ValueError()


def decode_fcdata(raw, *, received_at, source="ssi", profile="fcdata_v2"):
    """Return one canonical patch with field presence, source time and safe issues.

    `source=synthetic` is mandatory for fabricated fixtures. Missing keys stay absent;
    explicit null/invalid numbers become None. No old state is consulted.
    """
    if profile != "fcdata_v2":
        raise DecodeError("UNSUPPORTED_PROFILE: decoder này chỉ nhận FCData v2.")
    if source not in {"ssi", "synthetic"}:
        raise DecodeError("INVALID_SOURCE")
    try:
        received = timestamp(received_at)
    except (ValueError, TypeError, AttributeError):
        raise DecodeError("INVALID_RECEIVED_AT: cần ISO8601 có múi giờ.") from None
    outer = _index(_object(raw))
    content = _index(_object(outer["content"])) if "content" in outer else outer
    types = [obj[k] for obj,keys in ((outer,("datatype",)),(content,("rtype","datatype")))
             for k in keys if k in obj]
    if not types or any(not isinstance(t,str) for t in types):
        raise DecodeError("MISSING_TYPE: thiếu loại thông điệp.")
    kinds = {t.strip().upper() for t in types}
    if len(kinds)!=1:
        raise DecodeError("TYPE_CONFLICT: loại envelope và payload mâu thuẫn.")
    kind = kinds.pop()
    if kind not in SUPPORTED:
        raise DecodeError("UNSUPPORTED_TYPE: loại dữ liệu chưa được hỗ trợ.")
    symbol = content.get("symbol")
    if not isinstance(symbol,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}",symbol.strip()):
        raise DecodeError("INVALID_SYMBOL: thiếu hoặc sai mã chứng khoán.")
    payload = {"symbol":symbol.strip().upper()}
    issues = []
    mapped = {}

    def numeric(value, field):
        if value is None:
            return None
        if field.startswith(("bidPrice","askPrice")) and isinstance(value,str) and value.upper() in {"ATO","ATC"}:
            return value.upper()
        if isinstance(value,bool) or not isinstance(value,(int,float,str)):
            issues.append({"code":"INVALID_NUMBER","field":field})
            return None
        try:
            result=float(value)
            if not math.isfinite(result) or result<0:
                raise ValueError()
        except (ValueError,OverflowError):
            issues.append({"code":"INVALID_NUMBER","field":field})
            return None
        return result

    def assign(target, aliases, transform=None):
        present = [key.lower() for key in aliases if key.lower() in content]
        if not present:
            return
        values = [(transform(content[k],target) if transform else content[k]) for k in present]
        if any(v!=values[0] for v in values[1:]):
            raise DecodeError("ALIAS_CONFLICT: các trường cùng ý nghĩa có giá trị mâu thuẫn.")
        payload[target] = values[0]
        mapped[target] = present

    assign("marketCode",("MarketId","Exchange"),
        lambda v,_: v.strip().upper() if isinstance(v,str) and v.strip().upper() in {"HOSE","HNX","UPCOM","DER","HNXBOND"} else None)
    if "marketCode" not in payload or payload["marketCode"] is None:
        issues.append({"code":"MISSING_OR_UNKNOWN_MARKET","field":"marketCode"})
    if kind in {"F","X","X-QUOTE","X-TRADE"}:
        assign("tradingSession",("TradingSession",),
            lambda v,_: v.upper() if isinstance(v,str) and v.upper() in SESSIONS else None)
        assign("tradingStatus",("TradingStatus",),
            lambda v,_: {"N":"NORMAL","H":"HALT"}.get(v.upper()) if isinstance(v,str) else None)
        for key in ("tradingSession","tradingStatus"):
            if key in payload and payload[key] is None:
                issues.append({"code":"NULL_OR_UNKNOWN_STATUS","field":key})

    price_maps = {
        "openPrice":("Open",),"refPrice":("RefPrice",),"highPrice":("Highest","High"),
        "lowPrice":("Lowest","Low"),"averagePrice":("AvgPrice","Avg"),
        "closePrice":("LastPrice",),"lastTradeVolume":("LastVol",),
        "totalTradingVolume":("TotalVol",),"totalTradingValue":("TotalVal",),
    }
    if kind in {"X","X-TRADE"}:
        for target,aliases in price_maps.items():
            assign(target,aliases,numeric)
        # Close is retained separately: it is not silently substituted for LastPrice.
        assign("ohlcClosePrice",("Close",),numeric)
    if kind in {"X","X-QUOTE"}:
        for side in ("Bid","Ask"):
            for field in ("Price","Vol"):
                for level in (1,2,3):
                    assign(f"{side.lower()}{field}{level}",(f"{side}{field}{level}",),numeric)
    if kind=="R":
        for target,aliases in {
            "foreignBuyVolume":("FBuyVol","BuyVol"),"foreignSellVolume":("FSellVol","SellVol"),
            "foreignBuyValue":("FBuyVal","BuyVal"),"foreignSellValue":("FSellVal","SellVal"),
            "foreignRoom":("TotalRoom",),"foreignRemain":("CurrentRoom",),
        }.items():
            assign(target,aliases,numeric)
    if kind=="B":
        for target,aliases in {"openPrice":("Open",),"highPrice":("High",),"lowPrice":("Low",),
                               "closePrice":("Close",),"lastTradeVolume":("Volume",)}.items():
            assign(target,aliases,numeric)
        if "value" in content:
            issues.append({"code":"B_VALUE_NOT_CUMULATIVE","field":"Value"})

    source_at = None
    date_value=content.get("tradingdate")
    day=None
    if "tradingdate" in content:
        try:
            day=_date(date_value)
            payload["tradingDate"]=day.strftime("%d/%m/%Y")
        except ValueError:
            payload["tradingDate"]=None
            issues.append({"code":"INVALID_DATE","field":"tradingDate"})
    time_value=content.get("time",content.get("tradingtime"))
    if isinstance(time_value,str):
        try:
            if "T" in time_value or " " in time_value:
                dt=datetime.fromisoformat(time_value)
                dt=dt.replace(tzinfo=TZ) if dt.tzinfo is None else dt.astimezone(TZ)
                if "tradingdate" in content and (day is None or dt.date()!=day):
                    raise ValueError()
                day=dt.date()
            elif day:
                parsed=None
                for fmt in ("%H:%M:%S.%f","%H:%M:%S","%H%M%S"):
                    try:
                        parsed=datetime.strptime(time_value,fmt).time()
                        break
                    except ValueError:
                        pass
                if parsed is None:
                    raise ValueError()
                dt=datetime.combine(day,parsed,tzinfo=TZ)
            else:
                raise ValueError()
            source_at=dt.isoformat()
            payload["tradingDate"]=day.strftime("%d/%m/%Y")
        except ValueError:
            issues.append({"code":"INVALID_OR_INCOMPLETE_SOURCE_TIME","field":"source_at"})
    if source_at is None:
        issues.append({"code":"SOURCE_TIME_UNAVAILABLE","field":"source_at"})
    estimated = kind=="R" and payload.get("marketCode")=="HOSE"
    if estimated:
        issues.append({"code":"FOREIGN_VALUE_ESTIMATED","field":"foreignBuyValue/foreignSellValue"})
    return {"schema_version":"ssi-fcdata-v2-patch-1", "source":source,"profile":profile,"message_type":kind,
        "channel":"stockInfo","received_at":received.isoformat(),"source_at":source_at,
        "update_mode":"patch","payload":payload,"present_fields":sorted(payload),
        "field_updated_at":{key:source_at for key in mapped},
        "field_sources":mapped,"issues":issues,
        "metadata":{"book_levels":3 if kind in {"X","X-QUOTE"} else None,
            "price_unit":"VND_documented_pending_live_validation", "volume_unit":"pending_live_validation",
            "foreign_value_estimated":True if estimated else None,
            "counter_fields":[k for k in ("totalTradingVolume","totalTradingValue","foreignBuyVolume","foreignSellVolume") if k in payload]}}
