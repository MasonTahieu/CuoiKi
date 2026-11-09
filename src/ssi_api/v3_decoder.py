"""Stateless FastConnect V3 stream decoder. No network, merging, scoring or clock inference.

Wire format read from the official ``ssi-sdk`` 3.3.2 parsers (``models/streaming.py``):
``{"channel": "DATA", "topic": "trade.FPT", "data": {"s": "FPT", "t": ..., "p": ...}}``.
The SDK fills omitted numbers with 0; this decoder reads the raw frame instead so that an
absent field stays absent and an explicit null stays None. Output follows the same internal
record contract as the FCData v2 decoder, so journal, replay, quality and ranking are shared.
"""
import math
import re
from datetime import datetime, timedelta
from src.data.store import TZ, timestamp
from src.ssi_api.decoder import DecodeError, _object, _index

PROFILE = "fastconnect_v3"
SCHEMA = "ssi-v3-patch-1"
MESSAGE_TYPES = {"TRADE", "QUOTE", "ROOM", "MARKET_FLAG", "MASTER"}
BOARDS = {"HOSE", "HNX", "UPCOM", "DER", "DERIVATIVES"}
# Session flags documented by the SDK for ``market.flag`` (ATO/LO/ATC); other names are kept
# for the raw journal and only mapped when their meaning is unambiguous.
SESSION_FLAGS = {"ATO": "ATO", "LO": "LO", "ATC": "ATC", "PT": "PT", "PLO": "PT", "C": "C", "CLOSE": "C",
                 "CLOSED": "C", "BREAK": "BREAK", "LB": "BREAK", "INTERMISSION": "BREAK", "HALT": "HALT"}
BOOK_LEVELS = 3
SYMBOL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}")
TRADE_MAP = {"p": "closePrice", "q": "lastTradeVolume", "v": "totalTradingVolume", "o": "openPrice",
             "h": "highPrice", "l": "lowPrice", "a": "averagePrice"}
ROOM_MAP = {"bq": "foreignBuyVolume", "bv": "foreignBuyValue", "sq": "foreignSellVolume",
            "sv": "foreignSellValue", "tr": "foreignRoom", "cr": "foreignRemain"}
RETAINED = {"s", "t", "b", "f", "ref", "ce", "fl", "bids", "asks", *TRADE_MAP, *ROOM_MAP}


def message_type(topic, data):
    kind = topic.lower()
    if kind.startswith("trade.index.") or kind.endswith(("@1m", "@5m")):
        return None  # index ticks and candles are outside the four-factor contract
    if kind.startswith("trade."):
        return "TRADE"
    if kind.startswith("quote."):
        return "QUOTE"
    if kind.startswith("room."):
        return "ROOM"
    if kind == "market.flag":
        return "MARKET_FLAG"
    if kind.startswith("market.") and any(k in data for k in ("s", "ce", "fl", "ref")):
        return "MASTER"
    return None


def source_time(value, received):
    """Return (aware datetime in UTC+7, issue code or None). Never guesses a date silently."""
    if value is None or value == "" or isinstance(value, bool):
        return None, "SOURCE_TIME_UNAVAILABLE"
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit() and len(value.strip()) >= 10):
        number = float(value)
        if not math.isfinite(number) or number <= 0:
            return None, "INVALID_OR_INCOMPLETE_SOURCE_TIME"
        seconds = number / 1000 if number > 1e11 else number
        try:
            return datetime.fromtimestamp(seconds, TZ), None
        except (OverflowError, OSError, ValueError):
            return None, "INVALID_OR_INCOMPLETE_SOURCE_TIME"
    if not isinstance(value, str):
        return None, "INVALID_OR_INCOMPLETE_SOURCE_TIME"
    text = value.strip()
    if "T" in text or "-" in text or "/" in text or (" " in text and ":" in text):
        for fmt in (None, "%d/%m/%Y %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%d/%m/%Y %H:%M:%S.%f", "%Y/%m/%d %H:%M:%S.%f"):
            try:
                dt = datetime.fromisoformat(text) if fmt is None else datetime.strptime(text, fmt)
            except ValueError:
                continue
            return (dt.replace(tzinfo=TZ) if dt.tzinfo is None else dt.astimezone(TZ)), None
        return None, "INVALID_OR_INCOMPLETE_SOURCE_TIME"
    for fmt in ("%H:%M:%S.%f", "%H:%M:%S", "%H%M%S"):
        try:
            parsed = datetime.strptime(text, fmt).time()
        except ValueError:
            continue
        # Time of day only: the trading date comes from the local receive date and is flagged.
        dt = datetime.combine(received.date(), parsed, tzinfo=TZ)
        if dt > received + timedelta(hours=12):
            dt -= timedelta(days=1)
        return dt, "SOURCE_DATE_FROM_RECEIVED"
    return None, "INVALID_OR_INCOMPLETE_SOURCE_TIME"


def decode_v3(raw, *, received_at, source="ssi"):
    """Return one canonical patch for a V3 DATA frame. Board-wide messages carry ``scope``."""
    if source not in {"ssi", "synthetic"}:
        raise DecodeError("INVALID_SOURCE")
    try:
        received = timestamp(received_at)
    except (ValueError, TypeError, AttributeError):
        raise DecodeError("INVALID_RECEIVED_AT: cần ISO8601 có múi giờ.") from None
    outer = _index(_object(raw))
    topic = outer.get("topic")
    if not isinstance(topic, str) or not topic.strip():
        raise DecodeError("MISSING_TOPIC: frame V3 thiếu topic.")
    if "data" not in outer:
        raise DecodeError("MISSING_DATA: frame V3 thiếu data.")
    data = _index(_object(outer["data"]))
    kind = message_type(topic.strip(), data)
    if kind is None:
        raise DecodeError("UNSUPPORTED_TYPE: topic V3 chưa được hỗ trợ.")
    issues, mapped, metadata = [], {}, {}
    payload = {}
    scope = None

    def numeric(value, field):
        if value is None:
            return None
        if isinstance(value, str) and value.strip().upper() in {"ATO", "ATC"}:
            if field.startswith(("bidPrice", "askPrice")):
                return value.strip().upper()  # auction label in the book, same rule as FCData v2
            issues.append({"code": "AUCTION_PRICE_LABEL", "field": field})
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            issues.append({"code": "INVALID_NUMBER", "field": field})
            return None
        try:
            result = float(value)
            if not math.isfinite(result) or result < 0:
                raise ValueError()
        except (ValueError, OverflowError):
            issues.append({"code": "INVALID_NUMBER", "field": field})
            return None
        return result

    if kind == "MARKET_FLAG":
        board = data.get("b")
        board = board.strip().upper() if isinstance(board, str) else None
        if board not in BOARDS:
            raise DecodeError("INVALID_BOARD: market.flag thiếu hoặc sai sàn.")
        board = "DER" if board == "DERIVATIVES" else board
        scope = {"board": board}
        flag = data.get("f")
        session = SESSION_FLAGS.get(flag.strip().upper()) if isinstance(flag, str) else None
        if "f" in data:
            payload["tradingSession"] = session
            mapped["tradingSession"] = ["f"]
            metadata["raw_flag"] = flag if isinstance(flag, str) and len(flag) <= 16 else None
            if session is None:
                issues.append({"code": "NULL_OR_UNKNOWN_STATUS", "field": "tradingSession"})
        payload["marketCode"] = board
    else:
        symbol = data.get("s")
        if not isinstance(symbol, str) or not SYMBOL.fullmatch(symbol.strip()):
            raise DecodeError("INVALID_SYMBOL: thiếu hoặc sai mã chứng khoán.")
        payload["symbol"] = symbol.strip().upper()
        if isinstance(data.get("b"), str) and data["b"].strip().upper() in BOARDS:
            payload["marketCode"] = data["b"].strip().upper()

    def assign(target, key):
        if key in data:
            payload[target] = numeric(data[key], target)
            mapped[target] = [key]

    if kind == "TRADE":
        for key, target in TRADE_MAP.items():
            assign(target, key)
        avg, volume = payload.get("averagePrice"), payload.get("totalTradingVolume")
        if isinstance(avg, float) and isinstance(volume, float):
            # V3 trade ticks carry cumulative volume and average price but no cumulative value.
            payload["totalTradingValue"] = avg * volume
            mapped["totalTradingValue"] = ["a", "v"]
            metadata["derived_fields"] = {"totalTradingValue": "averagePrice*totalTradingVolume"}
            issues.append({"code": "TOTAL_VALUE_DERIVED", "field": "totalTradingValue"})
    elif kind == "QUOTE":
        for side, prefix in (("bids", "bid"), ("asks", "ask")):
            if side not in data:
                continue
            levels = data[side]
            if levels is None:
                levels = []
            if not isinstance(levels, list):
                issues.append({"code": "INVALID_BOOK", "field": side})
                levels = []
            metadata[f"{side}_levels_received"] = len(levels)
            for level in range(1, BOOK_LEVELS + 1):
                entry = levels[level - 1] if level <= len(levels) else None
                price = volume = None
                if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    price, volume = entry[0], entry[1]
                elif isinstance(entry, dict):
                    lowered = {k.lower(): v for k, v in entry.items() if isinstance(k, str)}
                    price = next((lowered[k] for k in ("p", "price") if k in lowered), None)
                    volume = next((lowered[k] for k in ("q", "v", "volume", "quantity") if k in lowered), None)
                elif entry is not None:
                    issues.append({"code": "INVALID_BOOK_LEVEL", "field": f"{prefix}Price{level}"})
                if entry is None:
                    issues.append({"code": "BOOK_LEVEL_MISSING", "field": f"{prefix}Price{level}"})
                payload[f"{prefix}Price{level}"] = numeric(price, f"{prefix}Price{level}")
                payload[f"{prefix}Vol{level}"] = numeric(volume, f"{prefix}Vol{level}")
                mapped[f"{prefix}Price{level}"] = [side]
                mapped[f"{prefix}Vol{level}"] = [side]
        metadata["book_levels"] = BOOK_LEVELS
    elif kind == "ROOM":
        for key, target in ROOM_MAP.items():
            assign(target, key)
        # V3 docs do not say whether foreign values are exchange-reported or estimated.
        metadata["foreign_value_estimated"] = None
        metadata["foreign_value_basis"] = "pending_live_validation"
    elif kind == "MASTER":
        assign("refPrice", "ref")

    at, time_issue = source_time(data.get("t"), received)
    if time_issue:
        issues.append({"code": time_issue, "field": "source_at"})
    if at is not None:
        payload["tradingDate"] = at.strftime("%d/%m/%Y")
    source_at = at.isoformat() if at is not None else None
    counters = [k for k in ("totalTradingVolume", "totalTradingValue", "foreignBuyVolume", "foreignSellVolume") if k in payload]
    metadata.update({"price_unit": "VND_per_sdk_doc_pending_live_validation", "volume_unit": "shares_pending_live_validation",
                     "counter_fields": counters, "topic": topic.strip()[:64]})
    metadata.setdefault("foreign_value_estimated", None)
    metadata.setdefault("book_levels", None)
    return {"schema_version": SCHEMA, "source": source, "profile": PROFILE, "message_type": kind,
            "channel": "stockInfo", "received_at": received.isoformat(), "source_at": source_at,
            "update_mode": "patch", "payload": payload, "present_fields": sorted(payload),
            "field_updated_at": {key: source_at for key in mapped}, "field_sources": mapped,
            "issues": issues, "metadata": metadata, "scope": scope}


def fan_out(decoded, members):
    """Copy a board-wide message (market.flag) onto every member of that board.

    The copies are what the collector journals as ``ssiDecoded``; replay therefore needs no
    board logic and the original frame is still kept once as ``ssiRaw``.
    """
    scope = decoded.get("scope")
    if not scope:
        return [decoded]
    board = scope["board"]
    copies = []
    for symbol, member in sorted(members.items()):
        if member["marketCode"] != board:
            continue
        item = {**decoded, "payload": {**decoded["payload"], "symbol": symbol},
                "metadata": {**decoded["metadata"], "fanout_board": board}, "scope": None}
        item["present_fields"] = sorted(item["payload"])
        copies.append(item)
    return copies


def retained_raw(frame_raw, decoded):
    """Keep only fields this decoder reads; never arbitrary text from the server."""
    outer = _index(_object(frame_raw))
    data = _index(_object(outer.get("data", {})))
    clean = {}
    for key, value in data.items():
        if key not in RETAINED:
            continue
        if key in {"bids", "asks"}:
            if isinstance(value, list):
                clean[key] = [list(v[:2]) if isinstance(v, (list, tuple)) else v for v in value[:10]
                              if isinstance(v, (list, tuple, dict))]
            continue
        if isinstance(value, (dict, list)) or (isinstance(value, float) and not math.isfinite(value)):
            value = None
        if isinstance(value, str) and len(value) > 40:
            value = None
        clean[key] = value
    return {"topic": decoded["metadata"]["topic"], "message_type": decoded["message_type"], "data": clean}
