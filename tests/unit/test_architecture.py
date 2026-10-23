"""SPEC-NF2005 모듈 분리 — 패키지 구조, 의존 규칙, 도메인 격리."""

from __future__ import annotations

from tests import archcheck
from tests.archcheck import ROOT, check_domain_literals, check_imports

AREAS = ["core", "data", "collect", "index", "rag", "services", "ui", "api"]


def test_tc_nf2005_01_packages_exist():
    for area in AREAS:
        assert (ROOT / "movielab" / area / "__init__.py").is_file(), f"movielab/{area} 패키지 없음"
    for module in ["config.py", "container.py", "core/domain.py", "data/domain_movie.py"]:
        assert (ROOT / "movielab" / module).is_file(), f"movielab/{module} 없음"
    assert (ROOT / "scripts" / "__init__.py").is_file()


def test_tc_nf2005_02_no_import_violations():
    violations = []
    for path in archcheck.python_files():
        rel = path.relative_to(ROOT).as_posix()
        violations += check_imports(path.read_text(encoding="utf-8"), rel)
    assert violations == [], "\n".join(map(str, violations))


def test_tc_nf2005_03_no_domain_literals_outside_data():
    violations = []
    for path in archcheck.python_files():
        rel = path.relative_to(ROOT).as_posix()
        violations += check_domain_literals(path.read_text(encoding="utf-8"), rel)
    assert violations == [], "\n".join(map(str, violations))


def test_tc_nf2005_04_checker_detects_violations():
    # rag는 data를 import 할 수 없다 (절대 · 상대 import 모두)
    assert check_imports("from movielab.data import movies\n", "movielab/rag/graph.py")
    assert check_imports("from ..data import movies\n", "movielab/rag/graph.py")
    # ui는 index를 직접 import 할 수 없다
    assert check_imports("import movielab.index.store\n", "movielab/ui/streamlit_app.py")
    # core는 외부 패키지(chromadb)를 쓸 수 없다
    assert check_imports("import chromadb\n", "movielab/core/types.py")
    # 허용되는 import는 통과
    assert not check_imports("from movielab.core import types\n", "movielab/rag/graph.py")
    assert not check_imports("from movielab.data import movies\n", "movielab/container.py")
    assert not check_imports("import json\nfrom langchain_core.documents import Document\n", "movielab/core/types.py")
    # 도메인 표현: data/ 밖은 위반, data/ 안 · docstring은 허용
    assert check_domain_literals('LABEL = "영화 메타데이터"\n', "movielab/rag/graph.py")
    assert check_domain_literals('KEY = "director"\n', "movielab/services/qa.py")
    assert not check_domain_literals('LABEL = "영화 메타데이터"\n', "movielab/data/domain_movie.py")
    assert not check_domain_literals('"""영화 설명 docstring"""\n', "movielab/rag/graph.py")
    assert not check_domain_literals('FILTER_KEY = "movie_id"\n', "movielab/rag/retriever.py")
