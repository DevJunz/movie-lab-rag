"""SPEC-NF2005 AC-05 — live가 아닌 테스트는 외부 네트워크에 연결할 수 없다."""

from __future__ import annotations

import socket

import pytest

from tests.conftest import NetworkBlockedError


def test_tc_nf2005_06_external_connection_blocked():
    with pytest.raises(NetworkBlockedError):
        socket.create_connection(("example.com", 80), timeout=1)
    with pytest.raises(NetworkBlockedError):
        socket.socket().connect(("93.184.216.34", 80))
    with pytest.raises(NetworkBlockedError):
        socket.gethostbyname("example.com")
    with pytest.raises(NetworkBlockedError):
        socket.gethostbyname_ex("example.com")


def test_tc_nf2005_06_loopback_allowed():
    left, right = socket.socketpair()
    try:
        left.sendall(b"ok")
        assert right.recv(2) == b"ok"
    finally:
        left.close()
        right.close()


def test_tc_nf2005_06_tracing_env_isolated():
    import os

    for name in (
        "LANGCHAIN_TRACING_V2",
        "LANGSMITH_TRACING_V2",
        "LANGCHAIN_ENDPOINT",
        "LANGSMITH_ENDPOINT",
    ):
        assert name not in os.environ
