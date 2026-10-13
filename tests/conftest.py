import pytest
import socket
import ipaddress
import httpx


@pytest.fixture(autouse=True)
def isolated_runtime_data(tmp_path, monkeypatch):
    """Every test uses its own data directory; tests never touch the real runtime_data/."""
    monkeypatch.setenv("WORKWELL_DATA_DIR", str(tmp_path / "runtime_data"))
    return tmp_path / "runtime_data"


@pytest.fixture(autouse=True)
def no_external_network_during_tests(monkeypatch):
    """The offline test suite must never spend model quota or contact a service."""
    original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex
    def local_only(original):
        def connect(sock, address):
            if sock.family == getattr(socket, "AF_UNIX", object()):
                return original(sock, address)
            if isinstance(address, tuple):
                try:
                    local = ipaddress.ip_address(address[0]).is_loopback
                except ValueError:
                    local = address[0] == "localhost"
                if local:
                    return original(sock, address)
            raise AssertionError("External network connections are disabled during offline tests.")
        return connect
    def blocked_http(*args, **kwargs):
        raise AssertionError("HTTP/model requests are disabled during offline tests.")
    async def blocked_async_http(*args, **kwargs):
        raise AssertionError("HTTP/model requests are disabled during offline tests.")
    monkeypatch.setattr(socket.socket, "connect", local_only(original_connect))
    monkeypatch.setattr(socket.socket, "connect_ex", local_only(original_connect_ex))
    monkeypatch.setattr(httpx.Client, "send", blocked_http)
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked_async_http)
