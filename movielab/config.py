"""설정 로드: `config/settings.json`(조정 값). 비밀 값(.env)은 SPEC-NF2003에서 더한다."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETTINGS_PATH = REPO_ROOT / "config" / "settings.json"
SETTINGS_ENV = "MOVIELAB_SETTINGS"


class SettingsError(ValueError):
    """설정 파일이 없거나 값이 잘못되었다."""


class Section:
    """설정 묶음 하나. `settings.chunking.chunk_size`처럼 속성으로 읽는다."""

    def __init__(self, name: str, values: dict[str, Any]) -> None:
        self._name = name
        self._values = values

    def __getattr__(self, key: str) -> Any:
        try:
            value = self._values[key]
        except KeyError:
            raise AttributeError(f"설정 '{self._name}.{key}'이 없다") from None
        return Section(f"{self._name}.{key}", value) if isinstance(value, dict) else value

    def as_dict(self) -> dict[str, Any]:
        return dict(self._values)


class Settings:
    """전체 설정. 상대 경로는 저장소 루트를 기준으로 푼다."""

    def __init__(self, raw: dict[str, Any], source: Path) -> None:
        self.raw = raw
        self.source = source

    def __getattr__(self, key: str) -> Section:
        if key in ("raw", "source"):
            raise AttributeError(key)
        try:
            return Section(key, self.raw[key])
        except KeyError:
            raise AttributeError(f"설정 묶음 '{key}'이 없다") from None

    def path(self, key: str) -> Path:
        value = Path(self.raw["paths"][key])
        return (value if value.is_absolute() else REPO_ROOT / value).resolve()


def load_settings(path: str | Path | None = None) -> Settings:
    """설정 파일을 읽는다. 경로를 주지 않으면 환경변수 `MOVIELAB_SETTINGS`, 그다음 기본 파일."""
    chosen = Path(path or os.environ.get(SETTINGS_ENV) or DEFAULT_SETTINGS_PATH)
    try:
        raw = json.loads(chosen.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SettingsError(f"설정 파일이 없다: {chosen}") from exc
    except json.JSONDecodeError as exc:
        raise SettingsError(f"설정 파일 형식 오류: {chosen} ({exc.msg})") from exc
    return Settings(raw, chosen)
