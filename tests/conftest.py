import ipaddress
import socket
import pytest


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    original = socket.socket.connect
    def connect(sock, address):
        try:
            local = address[0] == "localhost" or ipaddress.ip_address(address[0]).is_loopback
        except ValueError:
            local = False
        if not local:
            raise AssertionError("Kiểm thử offline không được gọi ra mạng.")
        return original(sock, address)
    monkeypatch.setattr(socket.socket, "connect", connect)
    for key in ("NEO_ACCESS_TOKEN", "NEO_DEVICE_ID", "NEO_WS_URL"):
        monkeypatch.setenv(key, "")
    monkeypatch.setenv("NEO_UPDATE_MODE", "snapshot")
    monkeypatch.setenv("NEO_WS_FORMAT", "bare")
    monkeypatch.setenv("NEO_SEMANTICS_VERIFIED", "false")
    monkeypatch.setenv("SSI_API_PROFILE", "unselected")
    monkeypatch.setenv("SSI_SEMANTICS_VERIFIED", "false")
