"""모듈 의존 규칙과 도메인 격리 규칙 검사기 (SPEC-NF2005 §3.2, §3.3).

01-architecture.md §2.1의 의존 규칙 표를 코드로 옮긴 것이다.
표를 바꾸면 이 파일도 같은 PR에서 바꾼다.
"""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "movielab"

# 영역 → import 해도 되는 movielab 내부 영역 (같은 영역 안의 import는 항상 허용)
ALLOWED_INTERNAL: dict[str, set[str]] = {
    "core": {"core"},
    "config": {"core"},
    "providers": {"core", "config"},
    "prompts": {"core"},
    "data": {"core", "config"},
    "collect": {"core", "config", "prompts", "collect"},
    "index": {"core", "config", "prompts", "index"},
    "rag": {"core", "config", "prompts", "rag"},
    "services": {"core", "config", "prompts", "collect", "index", "rag", "services"},
    "container": {"*"},
    "ui": {"core", "config", "services", "container", "ui"},
    "api": {"core", "config", "services", "container", "api"},
    "scripts": {"core", "config", "services", "container"},
}

# core가 쓸 수 있는 외부 패키지 (표준 라이브러리는 항상 허용)
CORE_THIRD_PARTY = {"langchain_core", "typing_extensions"}

# data/ 밖에서 문자열 리터럴로 나오면 안 되는 영화 도메인 표현
FORBIDDEN_LITERAL = re.compile(
    r"영화|\btmdb\b|\bdirector\b|\bcast\b|\boverview\b|\boriginal_title\b", re.IGNORECASE
)
# 금지 단어 검사 예외 파일 (기본 경로 문자열 — SPEC-NF2005 §3.2)
FORBIDDEN_EXEMPT = {"movielab/config.py"}


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


def area_of(rel_path: str) -> str | None:
    """파일 경로 → 영역. 예: `movielab/collect/x.py` → `collect`, `scripts/x.py` → `scripts`."""
    parts = Path(rel_path).with_suffix("").parts
    if parts[0] == "scripts":
        return "scripts"
    if parts[0] != PACKAGE or len(parts) < 2:
        return None
    if parts[1] == "__init__":
        return "core"
    return parts[1]


def _internal_target(module: str) -> str | None:
    parts = module.split(".")
    if parts[0] != PACKAGE:
        return None
    return parts[1] if len(parts) > 1 else "core"


def _imported_modules(tree: ast.AST, rel_path: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # 상대 import → 절대 경로로 바꾼다
                base = list(Path(rel_path).with_suffix("").parts[: -node.level])
                module = ".".join(base + ([node.module] if node.module else []))
            else:
                module = node.module or ""
            if module == PACKAGE:  # `from movielab import data` → movielab.data
                found += [(node.lineno, f"{PACKAGE}.{alias.name}") for alias in node.names]
            else:
                found.append((node.lineno, module))
    return found


def check_imports(source: str, rel_path: str) -> list[Violation]:
    area = area_of(rel_path)
    if area is None:
        return []
    allowed = ALLOWED_INTERNAL.get(area)
    if allowed is None:
        return [Violation(rel_path, 1, f"의존 규칙 표에 없는 영역 '{area}'")]
    violations: list[Violation] = []
    for line, module in _imported_modules(ast.parse(source), rel_path):
        if not module:
            continue
        target = _internal_target(module)
        if target is not None:
            if "*" not in allowed and target != area and target not in allowed:
                violations.append(
                    Violation(rel_path, line, f"'{area}'는 '{target}'를 import 할 수 없다")
                )
        elif area == "core":
            top = module.split(".")[0]
            if top not in sys.stdlib_module_names and top not in CORE_THIRD_PARTY:
                violations.append(
                    Violation(rel_path, line, f"'core'는 외부 패키지 '{top}'를 쓸 수 없다")
                )
    return violations


def _docstring_nodes(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def check_domain_literals(source: str, rel_path: str) -> list[Violation]:
    """`movielab/data/` 밖 코드의 문자열 리터럴에 영화 도메인 표현이 있으면 위반."""
    if not rel_path.startswith(f"{PACKAGE}/") or rel_path.startswith(f"{PACKAGE}/data/"):
        return []
    if rel_path in FORBIDDEN_EXEMPT:
        return []
    tree = ast.parse(source)
    docstrings = _docstring_nodes(tree)
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            match = FORBIDDEN_LITERAL.search(node.value)
            if match:
                violations.append(
                    Violation(
                        rel_path, node.lineno, f"도메인 표현 '{match.group(0)}'은 data/에만 둔다"
                    )
                )
    return violations


def literal_checker(
    pattern: str, *, exempt_data: bool = True
) -> Callable[[str, str], list[Violation]]:
    """`movielab/` 문자열 리터럴(docstring 제외)에서 정규식을 찾는 검사기를 만든다."""
    regex = re.compile(pattern, re.MULTILINE)

    def check(source: str, rel_path: str) -> list[Violation]:
        if not rel_path.startswith(f"{PACKAGE}/"):
            return []
        if exempt_data and rel_path.startswith(f"{PACKAGE}/data/"):
            return []
        tree = ast.parse(source)
        docstrings = _docstring_nodes(tree)
        return [
            Violation(
                rel_path, node.lineno, f"'{regex.search(node.value).group(0)}'은 data/에만 둔다"
            )
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
            and regex.search(node.value)
        ]

    return check


def python_files() -> list[Path]:
    files = sorted((ROOT / PACKAGE).rglob("*.py"))
    scripts = ROOT / "scripts"
    if scripts.exists():
        files += sorted(scripts.rglob("*.py"))
    return files


def scan_repo(*checkers: Callable[[str, str], list[Violation]]) -> list[Violation]:
    """저장소의 모든 소스에 검사기를 돌린다. 파일은 한 번만 읽는다."""
    checkers = checkers or (check_imports, check_domain_literals)
    violations: list[Violation] = []
    for path in python_files():
        rel = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        for checker in checkers:
            violations += checker(source, rel)
    return violations
