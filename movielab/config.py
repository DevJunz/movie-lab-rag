"""설정 로드: `config/settings.json`(조정 값) + `.env`(비밀 값, SPEC-NF2003)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from movielab.core.errors import MovieLabUserError

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETTINGS_PATH = REPO_ROOT / "config" / "settings.json"
SETTINGS_ENV = "MOVIELAB_SETTINGS"
DOTENV_PATH = REPO_ROOT / ".env"
MODEL_ENV = {"chat": "MOVIELAB_CHAT_MODEL", "embedding": "MOVIELAB_EMBED_MODEL"}


class SettingsError(MovieLabUserError, ValueError):
    """설정 파일이 없거나 값이 잘못되었다."""

    code = "SETTINGS_INVALID"


def read_env() -> dict[str, str]:
    """`.env` 값과 환경변수를 합친다. 같은 이름이면 환경변수가 이긴다.

    `os.environ`은 바꾸지 않는다 (테스트 사이 누출 방지, 실행 중 `.env` 수정 반영).
    """
    merged = {k: v for k, v in dotenv_values(DOTENV_PATH).items() if v is not None}
    merged.update({k: v for k, v in os.environ.items() if v.strip()})
    return merged


def _get(env: Mapping[str, str], name: str) -> str | None:
    value = (env.get(name) or "").strip()
    return value or None


@dataclass(frozen=True, repr=False)
class Secrets:
    """`.env` · 환경변수의 비밀 값. 출력할 때는 항상 가린다."""

    gms_api_key: str | None = None
    gms_base_url: str | None = None
    wiki_contact: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> Secrets:
        return cls(_get(env, "GMS_API_KEY"), _get(env, "GMS_BASE_URL"), _get(env, "WIKI_CONTACT"))

    @property
    def has_gms(self) -> bool:
        return bool(self.gms_api_key and self.gms_base_url)

    def __repr__(self) -> str:
        def mask(value: str | None) -> str:
            return "***" if value else "None"

        return (
            f"Secrets(gms_api_key={mask(self.gms_api_key)}, "
            f"gms_base_url={mask(self.gms_base_url)}, wiki_contact={mask(self.wiki_contact)})"
        )

    __str__ = __repr__


class Section:
    """설정 묶음 하나. `settings.chunking.chunk_size`처럼 속성으로 읽는다."""

    def __init__(self, name: str, values: dict[str, Any]) -> None:
        self._name = name
        self._values = values

    def __getattr__(self, key: str) -> Any:
        if key.startswith("_"):  # copy · pickle이 빈 인스턴스에서 특수 이름을 찾을 때 재귀 방지
            raise AttributeError(key)
        try:
            value = self._values[key]
        except KeyError:
            raise AttributeError(f"설정 '{self._name}.{key}'이 없다") from None
        return Section(f"{self._name}.{key}", value) if isinstance(value, dict) else value

    def as_dict(self) -> dict[str, Any]:
        return dict(self._values)


class Settings:
    """전체 설정. 상대 경로는 저장소 루트를 기준으로 푼다."""

    def __init__(self, raw: dict[str, Any], source: Path, secrets: Secrets | None = None) -> None:
        self.raw = raw
        self.source = source
        self.secrets = secrets or Secrets()

    def __repr__(self) -> str:
        return f"Settings(source={self.source.name}, secrets={self.secrets!r})"

    __str__ = __repr__

    def __getattr__(self, key: str) -> Section:
        if key.startswith("_") or key in ("raw", "source", "secrets"):
            raise AttributeError(key)
        try:
            return Section(key, self.raw[key])
        except KeyError:
            raise AttributeError(f"설정 묶음 '{key}'이 없다") from None

    def path(self, key: str) -> Path:
        value = Path(self.raw["paths"][key])
        return (value if value.is_absolute() else REPO_ROOT / value).resolve()


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _int_at_least(minimum: int) -> Callable[[Any], bool]:
    return lambda v: _is_int(v) and v >= minimum


def _number_at_least(minimum: float, *, strict: bool = False) -> Callable[[Any], bool]:
    return lambda v: _is_number(v) and (v > minimum if strict else v >= minimum)


# 묶음 → (키, 검사) — 묶음별 규칙은 해당 SPEC에서 더한다
_RULES: dict[str, list[tuple[str, Callable[[Any], bool]]]] = {
    "indexing": [  # SPEC-F2002
        ("batch_size", _int_at_least(1)),
        ("retries", _int_at_least(0)),
        ("retry_wait_sec", _number_at_least(0)),
    ],
    "cache": [  # SPEC-NF2002 (A-24)
        ("lock_timeout_sec", _number_at_least(0)),
        ("lock_poll_sec", _number_at_least(0, strict=True)),
        ("io_retries", _int_at_least(0)),
        ("io_retry_wait_sec", _number_at_least(0)),
    ],
    "retrieval": [  # SPEC-F2006 · F2014
        ("top_k", _int_at_least(1)),
        ("search_type", lambda v: v in ("similarity", "mmr")),
        ("mmr_fetch_k", _int_at_least(1)),
        ("mmr_lambda", lambda v: _is_number(v) and 0 <= v <= 1),
    ],
    "collect": [  # SPEC-F2003 · F2004
        ("source", lambda v: v in ("api", "bundle", "auto")),
        ("card_overview_chars", _int_at_least(1)),
        ("snippet_chars", _int_at_least(1)),
        ("intro_chars", _int_at_least(1)),
        ("bundle_snippet_radius", _int_at_least(1)),
        ("bundle_body_chars", _int_at_least(1)),
        ("min_queries", _int_at_least(0)),
        ("max_queries", _int_at_least(1)),
        ("search_limit", _int_at_least(1)),
        ("max_selected_docs", _int_at_least(0)),
        ("min_doc_chars", _int_at_least(0)),
    ],
    "chunking": [  # SPEC-F2005 (중복 < 크기는 _validate_chunking)
        ("chunk_size", _int_at_least(1)),
        ("chunk_overlap", _int_at_least(0)),
        ("pdf_chunk_size", _int_at_least(1)),
        ("pdf_chunk_overlap", _int_at_least(0)),
    ],
    "ui": [  # SPEC-F2008
        ("evidence_preview_chars", _int_at_least(1)),
    ],
    "wiki": [  # SPEC-NF2006
        ("max_retries", _int_at_least(0)),
        ("maxlag", _int_at_least(0)),
        ("min_interval_sec", _number_at_least(0)),
        ("backoff_base_sec", _number_at_least(0)),
        ("max_retry_after_sec", _number_at_least(0)),
        ("timeout_sec", _number_at_least(0, strict=True)),
        ("api_url", _is_text),
        ("app_name", _is_text),
        ("app_version", _is_text),
        ("project_url", _is_text),
    ],
}


def chunking_ok(size: Any, overlap: Any) -> bool:
    """청크 크기는 1 이상 정수, 중복은 0 이상 정수이고 크기보다 작아야 한다 (SPEC-F2005).

    설정 파일 검증과 재색인 스크립트의 일시 덮어쓰기 값이 같은 규칙을 쓴다.
    """
    return _is_int(size) and size >= 1 and _is_int(overlap) and 0 <= overlap < size


def _validate_chunking(raw: dict[str, Any], source: Path) -> None:
    """각 값의 타입 · 범위는 `_RULES`가 먼저 검사한다. 여기서는 중복 < 크기만 (SPEC-F2005)."""
    chunking = raw["chunking"]
    for size_key, overlap_key in (
        ("chunk_size", "chunk_overlap"),
        ("pdf_chunk_size", "pdf_chunk_overlap"),
    ):
        size, overlap = chunking[size_key], chunking[overlap_key]
        if not chunking_ok(size, overlap):
            raise SettingsError(
                f"설정 값 오류: chunking.{overlap_key}={overlap!r}는 0 이상, "
                f"{size_key}({size})보다 작아야 한다 ({source})"
            )


def _validate(raw: dict[str, Any], source: Path) -> None:
    """시작할 때 잡아야 하는 값 오류 — 타입까지 검사한다."""
    for group, rules in _RULES.items():
        section = raw.get(group)
        if not isinstance(section, dict):
            raise SettingsError(f"설정 값 오류: {group}은 객체여야 한다 ({source})")
        for name, ok in rules:
            value = section.get(name)
            if not ok(value):
                raise SettingsError(f"설정 값 오류: {group}.{name}={value!r} ({source})")
    _validate_chunking(raw, source)


def load_settings(path: str | Path | None = None) -> Settings:
    """설정 파일과 비밀 값을 읽는다.

    설정 파일: 인자 → 환경변수 `MOVIELAB_SETTINGS` → 기본 파일 순.
    비밀 값: 부를 때마다 `.env`를 읽고 환경변수와 합친다(환경변수 우선, `os.environ`은 그대로).
    """
    env = read_env()
    chosen = Path(path or os.environ.get(SETTINGS_ENV) or DEFAULT_SETTINGS_PATH)
    try:
        raw = json.loads(chosen.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SettingsError(f"설정 파일이 없다: {chosen}") from exc
    except json.JSONDecodeError as exc:
        raise SettingsError(f"설정 파일 형식 오류: {chosen} ({exc.msg})") from exc
    _validate(raw, chosen)
    for key, env_name in MODEL_ENV.items():
        override = _get(env, env_name)
        if override:
            raw.setdefault("models", {})[key] = override
    return Settings(raw, chosen, Secrets.from_env(env))
