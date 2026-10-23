"""저장소 비밀 값 유출 검사기 (SPEC-NF2003 §3.3)."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*[\"'][^\"'\s]{16,}[\"']"),
]
# 테스트용 가짜 키는 이 접두어로만 쓴다
ALLOWED_PREFIXES = ("sk-test",)
# 패턴 정의 자체가 들어 있는 파일
EXEMPT_FILES = {"tests/secret_scan.py"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".ico", ".sqlite3", ".bin"}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    text: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.text[:12]}…"


def scan_text(text: str, path: str = "<text>") -> list[Finding]:
    findings: list[Finding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for pattern in PATTERNS:
            for match in pattern.finditer(line):
                found = match.group(0)
                if any(prefix in found for prefix in ALLOWED_PREFIXES):
                    continue
                findings.append(Finding(path, number, found))
    return findings


def tracked_files(root: Path = ROOT) -> list[str]:
    """Git이 추적(또는 추가 예정)하는 파일. Git이 없으면 무시 파일을 뺀 전체."""
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
    skip = {".git", ".venv", "data", "logs", "reports", "영화도메인_데이터_배포용"}
    return [
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and not (set(p.relative_to(root).parts) & skip)
    ]


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
