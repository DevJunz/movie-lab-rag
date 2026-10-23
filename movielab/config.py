"""설정 로드: `config/settings.json`(조정 값) + `.env`(비밀 값, SPEC-NF2003)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETTINGS_PATH = REPO_ROOT / "config" / "settings.json"
SETTINGS_ENV = "MOVIELAB_SETTINGS"
DOTENV_PATH = REPO_ROOT / ".env"
MODEL_ENV = {"chat": "MOVIELAB_CHAT_MODEL", "embedding": "MOVIELAB_EMBED_MODEL"}


class SettingsError(ValueError):
    """설정 파일이 없거나 값이 잘못되었다."""


def _env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


@dataclass(frozen=True, repr=False)
class Secrets:
    """`.env` · 환경변수의 비밀 값. 출력할 때는 항상 가린다."""

    gms_api_key: str | None = None
    gms_base_url: str | None = None
    wiki_contact: str | None = None

    @classmethod
    def from_env(cls) -> Secrets:
        return cls(_env("GMS_API_KEY"), _env("GMS_BASE_URL"), _env("WIKI_CONTACT"))

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


def load_settings(path: str | Path | None = None) -> Settings:
    """설정 파일과 비밀 값을 읽는다.

    설정 파일: 인자 → 환경변수 `MOVIELAB_SETTINGS` → 기본 파일 순.
    비밀 값: `.env`를 읽되 이미 설정된 환경변수는 덮어쓰지 않는다.
    """
    load_dotenv(DOTENV_PATH, override=False)
    chosen = Path(path or os.environ.get(SETTINGS_ENV) or DEFAULT_SETTINGS_PATH)
    try:
        raw = json.loads(chosen.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SettingsError(f"설정 파일이 없다: {chosen}") from exc
    except json.JSONDecodeError as exc:
        raise SettingsError(f"설정 파일 형식 오류: {chosen} ({exc.msg})") from exc
    for key, env_name in MODEL_ENV.items():
        override = _env(env_name)
        if override:
            raw.setdefault("models", {})[key] = override
    return Settings(raw, chosen, Secrets.from_env())
