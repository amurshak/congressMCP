"""Unit tests for A7's instrument: the host-selective CONNECT proxy in
scripts/govinfo_search_acceptance.py.

The instrument itself must be tested (a finding is only as valid as the
instrument that produced it): a denied host is refused at CONNECT -- so
no egress ever happens and httpx surfaces a transport error, which is
exactly the govinfo_unreachable row's trigger class -- while an allowed
host is tunneled byte-for-byte. Everything here talks only to
127.0.0.1; the denied-host test performs no real network connection at
all (the refusal happens before any upstream dial).
"""
import importlib.util
import os
import socket
import sys
import threading

import httpx
import pytest

_HARNESS = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "scripts", "govinfo_search_acceptance.py")


def _load_proxy_class():
    spec = importlib.util.spec_from_file_location(
        "govinfo_search_acceptance", _HARNESS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.HostSelectiveProxy


HostSelectiveProxy = _load_proxy_class()


@pytest.fixture
def proxy():
    instance = HostSelectiveProxy(deny_hosts=["api.govinfo.gov"]).start()
    yield instance
    instance.stop()


def test_denied_host_is_refused_at_connect_as_transport_error(proxy):
    # httpx sees the 502 CONNECT refusal as a TransportError -- an
    # httpx.HTTPError subclass, i.e. precisely what search_bills'
    # unreachable row catches. No egress happens: the refusal precedes
    # any upstream dial.
    with pytest.raises(httpx.HTTPError):
        with httpx.Client(proxy=proxy.url, timeout=5.0) as client:
            client.get("https://api.govinfo.gov/search")
    assert proxy.denied == ["api.govinfo.gov"]
    assert proxy.tunneled == []


def test_allowed_host_tunnels_bytes_intact(proxy):
    # A local echo server stands in for "any other host": CONNECT to it
    # through the proxy, push bytes, and read them back through the
    # tunnel.
    ready = threading.Event()
    received = {}

    server = socket.create_server(("127.0.0.1", 0))
    port = server.getsockname()[1]

    def echo_once():
        server.settimeout(5)
        ready.set()
        conn, _ = server.accept()
        conn.settimeout(5)
        data = conn.recv(65536)
        received["data"] = data
        conn.sendall(b"ECHO:" + data)
        conn.close()

    thread = threading.Thread(target=echo_once, daemon=True)
    thread.start()
    ready.wait(5)

    with socket.create_connection(("127.0.0.1", proxy.port),
                                  timeout=5) as sock:
        sock.sendall(f"CONNECT 127.0.0.1:{port} HTTP/1.1\r\n"
                     f"Host: 127.0.0.1:{port}\r\n\r\n".encode())
        sock.settimeout(5)
        status = sock.recv(65536)
        assert b"200 Connection Established" in status
        sock.sendall(b"payload-through-tunnel")
        back = b""
        while not back.startswith(b"ECHO:payload-through-tunnel"):
            chunk = sock.recv(65536)
            if not chunk:
                break
            back += chunk

    thread.join(5)
    server.close()
    assert received["data"] == b"payload-through-tunnel"
    assert back.startswith(b"ECHO:payload-through-tunnel")
    assert proxy.tunneled == ["127.0.0.1"]
    assert proxy.denied == []


def test_non_connect_requests_are_rejected(proxy):
    with socket.create_connection(("127.0.0.1", proxy.port),
                                  timeout=5) as sock:
        sock.sendall(b"GET http://example.com/ HTTP/1.1\r\n"
                     b"Host: example.com\r\n\r\n")
        sock.settimeout(5)
        assert b"405" in sock.recv(65536)
    assert proxy.denied == [] and proxy.tunneled == []
