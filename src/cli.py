"""Explicit collection command; other commands operate locally."""
import argparse
import json
import sys
from pathlib import Path
from src.config import ConfigurationError, load_settings, PROJECT_ROOT
from src.providers import load_provider_settings
from src.neo_api.rest import NeoError
from src.data.demo import DEMO_LABEL, DemoDataError, load_demo
from src.data.synthetic import demo_events, demo_groups
from src.data.store import EventStore, read_events
from src.data.normalize import state_at, recorded_update_mode
from src.ranking.engine import rank_groups


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="VN30 Screener — SSI FastConnect")
    parser.add_argument("command", choices=["check", "demo", "readiness", "connection-plan", "demo-pipeline", "collect", "replay",
                                            "smoke-v3", "history-v3", "session-v3", "evaluate-v3"])
    parser.add_argument("--transport", choices=["rest", "ws"], default=None)
    parser.add_argument("--seconds", type=int, default=300)
    parser.add_argument("--otp-mode", choices=["none", "prompt", "smart"], help="Ghi đè SSI_OTP_MODE cho lần chạy này")
    parser.add_argument("--sessions", type=int, default=10, help="Số phiên lịch sử cho history-v3")
    parser.add_argument("--every", type=int, default=15, help="Khoảng phút giữa các mốc đánh giá (evaluate-v3)")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--run")
    parser.add_argument("--as-of", help="Mốc ISO8601 kèm +07:00")
    args = parser.parse_args()
    try:
        if args.command == "connection-plan":
            from src.ssi_api.connections import connection_plan
            print(json.dumps(connection_plan(),ensure_ascii=False,indent=2))
            return 0
        if args.command in {"smoke-v3","history-v3","session-v3"} and args.seconds < 1:
            raise ConfigurationError("--seconds phải dương.")
        settings = load_settings()
        neo = load_provider_settings(settings.provider)
        if args.command == "readiness":
            missing = neo.missing() if settings.provider == "ssi" else [key for key,value in [("NEO_ACCESS_TOKEN",neo.token),("NEO_DEVICE_ID",neo.device),("NEO_WS_URL",neo.ws_url)] if not value]
            result = {"provider":settings.provider,"network_called":False,"configured":not missing,
                "missing":missing,"profile":getattr(neo,"profile","neo"),"semantics_verified":neo.semantics_verified}
            if getattr(neo,"profile","") == "fastconnect_v3":
                import importlib.util
                result.update({"otp_mode":neo.otp_mode,"subscribe_mode":neo.subscribe_mode,
                    "ssi_sdk_installed":importlib.util.find_spec("ssi_sdk") is not None})
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 0
        if args.command == "evaluate-v3":
            from src.analytics.sessions import evaluate_daily, evaluate_journal
            from src.data.daily_store import read_daily
            from src.ssi_api.v3_ops import DAILY_DB
            journal = Path(args.db or neo.database)
            result = {"intraday": None, "daily": None}
            if journal.is_file():
                result["intraday"] = evaluate_journal(journal, every_minutes=args.every,
                                                      semantics_verified=neo.semantics_verified)
                details = result["intraday"].pop("details")
                result["intraday"]["update_intervals"] = {d["run"]: d["update_intervals"] for d in details}
            else:
                result["intraday_note"] = "Chưa có nhật ký stream trong phiên; chạy session-v3 trong giờ giao dịch."
            if DAILY_DB.is_file():
                result["daily"] = evaluate_daily(read_daily(DAILY_DB))
            output = PROJECT_ROOT / "evidence" / "v3_sessions" / "evaluation.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
            result["output"] = str(output)
            print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
            return 0
        if args.command in {"smoke-v3", "history-v3", "session-v3"} or (
                args.command == "collect" and settings.provider == "ssi" and getattr(neo,"profile","") == "fastconnect_v3"):
            if settings.provider != "ssi":
                raise ConfigurationError("Lệnh V3 cần DATA_PROVIDER=ssi.")
            neo.validate_v3()
            if args.command == "collect" and args.transport == "rest":
                raise ConfigurationError("Với V3 dùng history-v3 cho REST và collect --transport ws cho stream.")
            from getpass import getpass
            from src.ssi_api import v3_ops
            mode = args.otp_mode or ("none" if args.command == "history-v3" else None)
            client = v3_ops.login(neo, mode, read_otp=lambda: getpass("OTP: "))
            try:
                if args.command == "smoke-v3":
                    result = v3_ops.smoke(neo, client, seconds=args.seconds)
                elif args.command == "history-v3":
                    result = v3_ops.history(neo, client, sessions=args.sessions)
                elif args.command == "session-v3":
                    result = v3_ops.session(neo, client)
                else:
                    result = v3_ops.collect(neo, client, seconds=args.seconds)
            finally:
                client.close()
            print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
            return 0
        if args.command == "collect":
            if settings.provider == "ssi":
                if args.transport == "ws":
                    raise ConfigurationError("Streaming SSI chờ xác nhận phiên bản/quyền được cấp; chưa chuyển giao thức NEO sang SSI.")
                from src.ssi_api.collector import collect_rest
                result = collect_rest(neo)
            else:
                from src.collector import collect
                result = collect(neo,args.seconds,args.transport or "ws")
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 0
        if args.command in {"demo-pipeline", "replay"}:
            if args.command == "demo-pipeline":
                path = args.db or PROJECT_ROOT / "runtime" / "synthetic.sqlite"
                store = EventStore(path)
                try:
                    for e in (demo_groups() if settings.provider == "ssi" else demo_events()):
                        store.append(**e)
                finally:
                    store.close()
                events = read_events(path, "synthetic-vn30-v1" if settings.provider == "ssi" else "synthetic-v1")
            else:
                events = read_events(args.db or neo.database, args.run)
            if not events:
                raise ValueError("Lần thu thập được chọn chưa có dữ liệu.")
            frame = state_at(events, args.as_of, update_mode=recorded_update_mode(events, neo.update_mode))
            ranks = rank_groups(frame, semantics_verified=neo.semantics_verified)
            output = PROJECT_ROOT / "runtime" / ("synthetic_ranking.csv" if events[0]["source"] == "synthetic" else events[0]["source"] + "_ranking.csv")
            output.parent.mkdir(parents=True, exist_ok=True)
            ranks.to_csv(output, index=False, encoding="utf-8-sig")
            print(json.dumps({"source":events[0]["source"], "run":events[0]["run"], "events":len(events),
                "symbols":len(frame), "ranked":int(ranks["rank"].notna().sum()) if not ranks.empty else 0,
                "network_called":False, "output":str(output)}, ensure_ascii=False, indent=2))
            return 0
        frame = load_demo()
        print(DEMO_LABEL)
        if args.command == "demo":
            print(frame.to_string(index=False))
        else:
            print(json.dumps({"mode":settings.mode, "timezone":settings.timezone,
                "rows":len(frame), "symbols":int(frame["symbol"].nunique()),
                "source":"synthetic", "provider":settings.provider, "network_called":False}, ensure_ascii=False, indent=2))
        return 0
    except (ConfigurationError, DemoDataError, NeoError, ValueError, OSError) as error:
        print(str(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
