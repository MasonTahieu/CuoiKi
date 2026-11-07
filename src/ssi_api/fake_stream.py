"""Offline transport. Script contents cannot relabel this transport as live SSI."""
from copy import deepcopy
from datetime import timedelta
from src.data.store import timestamp
from src.ssi_api.stream_collector import Frame, StreamDisconnected, StreamAuthFailed


class FakeClock:
    def __init__(self,start_at="2026-11-04T10:00:00+07:00"):
        self.value=0.
        self.origin=timestamp(start_at)
    def monotonic(self):return self.value
    def sleep(self,seconds):self.value+=seconds
    def wall_now(self):return (self.origin+timedelta(seconds=self.value)).isoformat()


class FakeSession:
    def __init__(self,script,clock):
        self.script=iter(script)
        self.clock=clock
        self.channels=()
        self.closed=False
        self.connected=False
        self.pending=None
    def connect(self):self.connected=True
    def subscribe(self,channels):self.channels=channels
    def receive(self,timeout):
        if not self.connected or self.closed:
            raise StreamDisconnected()
        try:item=self.pending if self.pending is not None else next(self.script)
        except StopIteration:
            self.clock.sleep(timeout)
            return None
        if isinstance(item,Exception):raise item
        if item is None:
            self.clock.sleep(timeout)
            return None
        if isinstance(item,Frame):
            due=max(self.clock.value,(timestamp(item.received_at)-self.clock.origin).total_seconds())
            if due>self.clock.value+timeout:
                self.pending=item
                self.clock.sleep(timeout)
                return None
            self.clock.value=due
        self.pending=None
        return deepcopy(item)
    def close(self):self.closed=True


class FakeFactory:
    source="synthetic"
    def __init__(self,members,scripts,clock):
        self.members=members
        self.scripts=iter(scripts)
        self.clock=clock
        self.sessions=[]
        self.bootstrap_calls=0
    def bootstrap(self):
        self.bootstrap_calls+=1
        return deepcopy(self.members)
    def create(self):
        try:script=next(self.scripts)
        except StopIteration:script=[StreamDisconnected()]
        stream=FakeSession(script,self.clock)
        self.sessions.append(stream)
        return stream
