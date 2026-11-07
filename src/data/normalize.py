"""Deterministic state reconstruction; absent fields differ from explicit null."""
import math
from datetime import datetime
import pandas as pd
from src.data.store import timestamp

NUMERIC = ["closePrice", "openPrice", "refPrice", "highPrice", "lowPrice", "averagePrice",
           "totalTradingVolume", "totalTradingValue", "foreignBuyValue", "foreignSellValue",
           "foreignBuyVolume", "foreignSellVolume", "ptTotalTradedValue"] + [
    f"{side}{kind}{level}" for side in ("bid", "ask") for kind in ("Price", "Vol") for level in (1,2,3)]
REQUIRED = ["closePrice", "openPrice", "totalTradingValue", "foreignBuyValue", "foreignSellValue"] + [
    f"{side}{kind}{level}" for side in ("bid", "ask") for kind in ("Price", "Vol") for level in (1,2,3)]


def number(value):
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def trading_day(value):
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            pass
    return None


def recorded_update_mode(events, fallback="snapshot"):
    modes = {e["payload"]["update_mode"] for e in events if e["channel"] == "connection"
             and "update_mode" in e["payload"]}
    if len(modes) > 1 or modes - {"snapshot", "patch"}:
        raise ValueError("Nhật ký có chế độ cập nhật không nhất quán.")
    return next(iter(modes)) if modes else fallback


def state_at(events, as_of=None, update_mode="snapshot", max_age=60):
    if update_mode not in {"snapshot", "patch"}:
        raise ValueError("Chế độ cập nhật không hợp lệ.")
    if not events:
        return pd.DataFrame()
    sources = {e["source"] for e in events}
    runs = {e["run"] for e in events}
    if len(sources) != 1 or len(runs) != 1:
        raise ValueError("Không trộn dữ liệu giả lập/thật hoặc nhiều lần thu thập.")
    cutoff = timestamp(as_of or max(e["received_at"] for e in events))
    states, sessions, universe, seen = {}, {}, {}, set()
    for e in events:
        at = timestamp(e["received_at"])
        if at > cutoff or at.date() != cutoff.date():
            continue
        channel, payload = e["channel"], e["payload"]
        identity = (e["received_at"], channel, str(payload))
        if identity in seen:
            continue
        seen.add(identity)
        if channel == "connection":
            if payload.get("state") in {"connecting", "disconnected", "auth_failed"}:
                states, sessions, universe = {}, {}, {}
            continue
        if channel == "universe":
            universe = {r["symbol"]: r for r in payload["members"]}
            continue
        if channel == "marketSession":
            market = payload.get("marketCode")
            if market not in sessions or at >= sessions[market][1]:
                sessions[market] = (payload.get("marketStatus"), at)
            continue
        if channel != "stockInfo" or payload.get("symbol") not in universe:
            continue
        symbol = payload["symbol"]
        old = states.get(symbol)
        if old and at < old["_at"]:
            continue  # late arrival by captured timestamp; source latency remains unverified
        metadata = universe[symbol]
        day = trading_day(payload.get("tradingDate", metadata.get("tradingDate")))
        if day != cutoff.date():
            continue
        patch = update_mode == "patch" and not e.get("full_snapshot", False)
        values = dict(old["_values"]) if old and patch else {}
        clocks = dict(old["_clocks"]) if old and patch else {}
        for key in NUMERIC:
            if key in payload:
                values[key] = number(payload[key])
                clocks[key] = at
        auction = any(str(payload.get(k, "")).upper() in {"ATO", "ATC"} for k in ("bidPrice1", "askPrice1"))
        rollback = bool(old and old.get("_rollback"))
        if old:
            for key in ("totalTradingVolume", "totalTradingValue", "foreignBuyValue", "foreignSellValue"):
                before, after = old["_values"].get(key), values.get(key)
                if before is not None and after is not None and after < before:
                    rollback = True
        states[symbol] = {"_values": values, "_clocks": clocks, "_at": at,
            "_auction": auction, "_rollback": rollback, "tradingStatus": payload.get("tradingStatus", metadata.get("tradingStatus")),
            "marketCode": metadata.get("marketCode"), "symbol": symbol}
    output = []
    for symbol, meta in universe.items():
        state = states.get(symbol)
        reasons = []
        row = {"symbol": symbol, "source": next(iter(sources)), "run": next(iter(runs)),
               "index_group":meta.get("index_group","VN30"), "marketCode":meta.get("marketCode"),
               "as_of": cutoff.isoformat(), "time_basis": "received_at", "trading_date": str(cutoff.date())}
        row.update({key: None for key in NUMERIC})
        if not state:
            reasons.append("chưa có snapshot đúng ngày")
        else:
            row.update(state["_values"])
            row["received_at"] = state["_at"].isoformat()
            row["age_seconds"] = (cutoff - state["_at"]).total_seconds()
            missing = [k for k in REQUIRED if row[k] is None]
            stale = [k for k in REQUIRED if k in state["_clocks"] and (cutoff-state["_clocks"][k]).total_seconds() > max_age]
            if missing:
                reasons.append("thiếu/sai trường: " + ", ".join(missing))
            if stale:
                reasons.append("trường dữ liệu cũ: " + ", ".join(stale))
            if state["_auction"]:
                reasons.append("giá ATO/ATC")
            if state["_rollback"]:
                reasons.append("số liệu cộng dồn giảm; chờ đối chiếu và khởi tạo lại")
            if state["tradingStatus"] != "NORMAL":
                reasons.append("trạng thái cổ phiếu chưa NORMAL")
        session = sessions.get(meta.get("marketCode"), (None, None))[0]
        row["session"] = session
        if session != "LO":
            reasons.append("ngoài phiên liên tục/chưa biết phiên")
        row["quality_reason"] = "; ".join(reasons)
        output.append(row)
    return pd.DataFrame(output)
