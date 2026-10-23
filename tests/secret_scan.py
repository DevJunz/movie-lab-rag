"""저장소 비밀 값 유출 검사기 (SPEC-NF2003 §3.3).

찾은 값은 어디에도 출력하지 않는다 — 공개 CI 로그에 키 일부가 남지 않게 하기 위해서다.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (이름, 정규식, 값 그룹 번호). 값 그룹은 예외 접두어 비교에 쓴다.
PATTERNS: list[tuple[str, re.Pattern[str], int]] = [
    ("OpenAI 형식 키", re.compile(r"sk-[A-Za-z0-9_-]{20,}"), 0),
    (
        "따옴표 값",
        re.compile(r"(?i)(?:api[_-]?key|secret|token)\s*[:=]\s*[\"']([^\"'\s]{16,})[\"']"),
        1,
    ),
    (
        ".env 줄",
        re.compile(
            r"^\s*(?:export\s+)?[A-Z0-9_]*(?:API_KEY|SECRET|TOKEN)[A-Z0-9_]*\s*=\s*"
            r"[\"']?([A-Za-z0-9_\-./+=]{20,})[\"']?\s*(?:#.*)?$"
        ),
        1,
    ),
]
# 테스트용 가짜 키는 이 접두어로 "시작"해야 한다 (포함이 아니다)
ALLOWED_PREFIXES = ("sk-test",)
# 패턴 정의 자체가 들어 있는 파일
EXEMPT_FILES = {"tests/secret_scan.py"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".ico", ".sqlite3", ".bin"}

# Git이 없을 때 건너뛸 폴더 · 파일 (.gitignore와 같은 취지)
FALLBACK_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "data",
    "logs",
    "reports",
    "영화도메인_데이터_배포용",
}
FALLBACK_SKIP_FILES = {"prd.pdf", "rag_project_briefing.html"}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.kind} 형태의 비밀 값"


def scan_text(text: str, path: str = "<text>") -> list[Finding]:
    findings: list[Finding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for kind, pattern, group in PATTERNS:
            for match in pattern.finditer(line):
                if match.group(group).startswith(ALLOWED_PREFIXES):
                    continue
                findings.append(Finding(path, number, kind))
    return findings


def _is_env_file(name: str) -> bool:
    return (name == ".env" or name.startswith(".env.")) and name != ".env.example"


def tracked_files(root: Path = ROOT) -> list[str]:
    """Git이 추적(또는 추가 예정)하는 파일. Git이 없으면 무시 대상을 뺀 전체."""
    if shutil.which("git") and (root / ".git").exists():
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        return [line for line in result.stdout.splitlines() if line]
    files: list[str] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if not path.is_file() or set(rel.parts[:-1]) & FALLBACK_SKIP_DIRS:
            continue
        if _is_env_file(path.name) or path.name in FALLBACK_SKIP_FILES:
            continue
        files.append(rel.as_posix())
    return files


def scan_repo(root: Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []
    for rel in tracked_files(root):
        path = root / rel
        if rel in EXEMPT_FILES or path.suffix.lower() in BINARY_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        findings += scan_text(text, rel)
    return findings
