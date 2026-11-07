import json
from dataclasses import replace
import pytest
import websocket
import src.collector as module
from src.data.store import read_events
from src.data.synthetic import demo_events
from src.neo_api.settings import NeoSettings
from src.neo_api.rest import AuthError, NeoError


class FakeRest:
    calls = 0
    def __init__(self, settings):
        pass
    def vn30(self):
        FakeRest.calls += 1
        return [e["payload"] for e in demo_events()[2:14]]
    def get(self, name, **params):
        return {"data":[{"marketCode":"HOSE","marketStatus":"LO"}]}
    def close(self):
        pass


@pytest.fixture
def mock_collector(monkeypatch, tmp_path):
    tick = [0.]
    monkeypatch.setattr(module.time,"monotonic",lambda:tick[0])
    monkeypatch.setattr(module.time,"sleep",lambda delay:tick.__setitem__(0,tick[0]+delay))
    monkeypatch.setattr(module,"RestClient",FakeRest)
    FakeRest.calls = 0
    settings = NeoSettings(token="SECRET_SENTINEL",device="test",database=tmp_path/"neo.sqlite",
        ws_url="wss://neoapi.vpbanks.com.vn/stock-stream/broker")
    return settings,tick


class FakeSocket:
    def __init__(self,tick,auth="success",fail=False):
        self.tick,self.auth,self.fail=tick,auth,fail
        self.messages,self.received,self.closed=[],0,False
    def send(self,data):
        self.messages.append(json.loads(data))
    def recv(self):
        self.received+=1
        if self.received == 1:
            return json.dumps({"type":"auth","status":self.auth,"data":{"username":"PRIVATE_ACCOUNT"}})
        if self.fail:
            raise websocket.WebSocketConnectionClosedException("PRIVATE_FAILURE")
        self.tick[0]+=2
        return json.dumps(demo_events()[2]["payload"])
    def settimeout(self,value):
        pass
    def ping(self):
        pass
    def close(self):
        self.closed=True


def test_successful_collector_auth_subscribe_store_without_secrets(mock_collector,monkeypatch):
    settings,tick=mock_collector
    sock=FakeSocket(tick)
    calls=[]
    def factory(url,**kwargs):
        calls.append((url,kwargs))
        return sock
    monkeypatch.setattr(module.websocket,"create_connection",factory)
    report=module.collect(settings,seconds=1)
    assert report["messages"] == 1 and sock.closed
    assert sock.messages[0] == {"action":"auth","data":"SECRET_SENTINEL"}
    assert [m["channel"] for m in sock.messages[1:]] == ["stockInfo","marketSession"]
    assert calls[0][1]["redirect_limit"] == 0
    events=read_events(settings.database)
    assert all(e["source"] == "neo" for e in events)
    assert "SECRET_SENTINEL" not in json.dumps(events)
    assert "PRIVATE_ACCOUNT" not in json.dumps(events)


def test_auth_failure_never_subscribes_or_retries(mock_collector,monkeypatch):
    settings,tick=mock_collector
    sock=FakeSocket(tick,auth="error")
    monkeypatch.setattr(module.websocket,"create_connection",lambda *a,**kw:sock)
    with pytest.raises(AuthError):
        module.collect(settings,seconds=30)
    assert len(sock.messages) == 1 and sock.closed
    assert FakeRest.calls == 1
    assert read_events(settings.database)[-1]["payload"]["state"] == "auth_failed"


def test_disconnect_resnapshots_and_resubscribes(mock_collector,monkeypatch):
    settings,tick=mock_collector
    sockets=[FakeSocket(tick,fail=True),FakeSocket(tick)]
    pending=iter(sockets)
    monkeypatch.setattr(module.websocket,"create_connection",lambda *a,**kw:next(pending))
    module.collect(settings,seconds=2)
    assert FakeRest.calls == 2
    assert all(s.closed for s in sockets)
    assert all(len(s.messages) == 3 for s in sockets)
    states=[e["payload"]["state"] for e in read_events(settings.database) if e["channel"] == "connection"]
    assert "disconnected" in states and states.count("connecting") == 2


def test_rest_probe_does_not_open_websocket(mock_collector,monkeypatch):
    settings,_=mock_collector
    def forbidden(*args,**kwargs):
        raise AssertionError("REST probe must not open WebSocket")
    monkeypatch.setattr(module.websocket,"create_connection",forbidden)
    report=module.collect(replace(settings,ws_url=""),transport="rest")
    assert report["symbols"] == 12 and report["transport"] == "rest"
