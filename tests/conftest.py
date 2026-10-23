"""공통 픽스처 (01-architecture.md §10.4)."""

from __future__ import annotations

import json
import logging
import shutil
import socket
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[1]

_LOOPBACK = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}
_ISOLATED_ENV = (
    "GMS_API_KEY",
    "GMS_BASE_URL",
    "WIKI_CONTACT",
    "LANGSMITH_API_KEY",
    "LANGCHAIN_API_KEY",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "MOVIELAB_SETTINGS",
    "MOVIELAB_CHAT_MODEL",
    "MOVIELAB_EMBED_MODEL",
    "LANGCHAIN_TRACING_V2",
    "LANGSMITH_TRACING_V2",
    "LANGCHAIN_ENDPOINT",
    "LANGSMITH_ENDPOINT",
)


class NetworkBlockedError(RuntimeError):
    """live 마커가 없는 테스트에서 외부 네트워크에 연결하려 했다."""


def _host(address: object) -> str:
    return str(address[0]) if isinstance(address, tuple) else str(address)


@pytest.fixture(autouse=True)
def _block_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """외부 연결을 막는다. 루프백은 허용한다 (Windows의 socketpair가 루프백 연결을 쓴다)."""
    if request.node.get_closest_marker("live"):
        return
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo

    def _allowed(sock: socket.socket, address: object) -> bool:
        return sock.family == getattr(socket, "AF_UNIX", object()) or _host(address) in _LOOPBACK

    def connect(self: socket.socket, address: object) -> None:
        if not _allowed(self, address):
            raise NetworkBlockedError(f"테스트에서 외부 연결 시도: {address}")
        return real_connect(self, address)

    def connect_ex(self: socket.socket, address: object) -> int:
        if not _allowed(self, address):
            raise NetworkBlockedError(f"테스트에서 외부 연결 시도: {address}")
        return real_connect_ex(self, address)

    def getaddrinfo(host: object, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        if host is not None and str(host) not in _LOOPBACK:
            raise NetworkBlockedError(f"테스트에서 외부 주소 조회 시도: {host}")
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    for name in ("gethostbyname", "gethostbyname_ex"):
        real = getattr(socket, name)

        def guarded(host: str, _real=real, _name=name):  # type: ignore[no-untyped-def]
            if str(host) not in _LOOPBACK:
                raise NetworkBlockedError(f"테스트에서 외부 주소 조회 시도({_name}): {host}")
            return _real(host)

        monkeypatch.setattr(socket, name, guarded)


@pytest.fixture(autouse=True)
def _fresh_shared_throttles(monkeypatch: pytest.MonkeyPatch) -> None:
    """프로세스 공용 위키 throttle이 테스트 사이에 남지 않게 한다 (NF2006)."""
    import movielab.data.wiki_api

    monkeypatch.setattr(movielab.data.wiki_api, "_SHARED", {})


@pytest.fixture(autouse=True)
def _isolate_env(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """실제 키 · 설정이 테스트에 새지 않게 환경변수를 지우고, 저장소의 .env를 읽지 않게 한다.

    live 테스트는 실제 키가 필요하므로 격리하지 않는다.
    """
    if request.node.get_closest_marker("live"):
        return
    import movielab.config

    monkeypatch.setattr(movielab.config, "DOTENV_PATH", tmp_path / "no-such.env")
    for name in _ISOLATED_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("ANONYMIZED_TELEMETRY", "False")


@pytest.fixture
def movies_small_path() -> Path:
    return FIXTURES / "movies_small.json"


@pytest.fixture
def movies_small(movies_small_path: Path) -> list[dict]:
    """합성 영화 12편: 동명 영화 2쌍, 감독 빈 목록 1편, 한국 영화 6편(1990년대 1편)."""
    return json.loads(movies_small_path.read_text(encoding="utf-8"))


@pytest.fixture
def wiki_small_dir() -> Path:
    """합성 위키 문서: 공유 문서, 동명 동화 문서, 200자 미만 문서, 동음이의 문서 포함."""
    return FIXTURES / "wiki_small"


@pytest.fixture(autouse=True)
def _remove_log_handlers():
    """스크립트 테스트가 붙인 로그 파일 핸들러를 테스트마다 떼어 낸다 (SPEC-NF2004)."""
    yield
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "movielab", False):
            root.removeHandler(handler)
            handler.close()


@pytest.fixture
def tmp_settings(tmp_path: Path, movies_small_path: Path, wiki_small_dir: Path):
    """임시 폴더를 가리키는 설정. 영화 · 위키 경로는 합성 픽스처를 쓴다."""
    from movielab.config import load_settings

    raw = json.loads((REPO_ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
    data_dir = tmp_path / "data"
    raw["paths"].update(
        {
            "movies": str(movies_small_path),
            "wiki_bundle": str(wiki_small_dir),
            "chroma_dir": str(data_dir / "chroma"),
            "raw_dir": str(data_dir / "raw"),
            "manifest": str(data_dir / "manifest.json"),
            "pdf_dir": str(data_dir / "pdf"),
            "pdf_manifest": str(data_dir / "pdf" / "pdf_manifest.json"),
            "log_file": str(tmp_path / "logs" / "movielab.log"),
        }
    )
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return load_settings(path)


@pytest.fixture
def copy_fixture(tmp_path: Path):
    """픽스처 파일 · 폴더를 임시 폴더로 복사해 경로를 돌려준다 (원본 보호)."""

    def _copy(name: str) -> Path:
        src = FIXTURES / name
        dst = tmp_path / name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy(src, dst)
        return dst

    return _copy
