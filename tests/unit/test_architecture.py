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
    violations = archcheck.scan_repo(check_imports)
    assert violations == [], "\n".join(map(str, violations))


def test_tc_nf2005_03_no_domain_literals_outside_data():
    violations = archcheck.scan_repo(check_domain_literals)
    assert violations == [], "\n".join(map(str, violations))


def test_tc_nf2005_04_checker_detects_violations():
    # rag는 data를 import 할 수 없다 (절대 · 상대 import 모두)
    assert check_imports("from movielab.data import movies\n", "movielab/rag/graph.py")
    assert check_imports("from ..data import movies\n", "movielab/rag/graph.py")
    # 패키지 루트에서 이름으로 가져오는 형태도 잡는다 (PR #24 리뷰)
    assert check_imports("from movielab import data\n", "movielab/rag/graph.py")
    assert check_imports("from .. import container\n", "movielab/rag/graph.py")
    assert check_imports("from movielab import core, data\n", "movielab/rag/graph.py")
    assert not check_imports("from movielab import core\n", "movielab/rag/graph.py")
    # 같은 영역 안의 import는 허용
    assert not check_imports("from movielab.data import movies\n", "movielab/data/domain_movie.py")
    # ui는 index를 직접 import 할 수 없다
    assert check_imports("import movielab.index.store\n", "movielab/ui/streamlit_app.py")
    # core는 외부 패키지(chromadb)를 쓸 수 없다
    assert check_imports("import chromadb\n", "movielab/core/types.py")
    # 허용되는 import는 통과
    assert not check_imports("from movielab.core import types\n", "movielab/rag/graph.py")
    assert not check_imports("from movielab.data import movies\n", "movielab/container.py")
    assert not check_imports(
        "import json\nfrom langchain_core.documents import Document\n", "movielab/core/types.py"
    )
    # 도메인 표현: data/ 밖은 위반, data/ 안 · docstring은 허용
    assert check_domain_literals('LABEL = "영화 메타데이터"\n', "movielab/rag/graph.py")
    assert check_domain_literals('KEY = "director"\n', "movielab/services/qa.py")
    assert not check_domain_literals('LABEL = "영화 메타데이터"\n', "movielab/data/domain_movie.py")
    assert not check_domain_literals('"""영화 설명 docstring"""\n', "movielab/rag/graph.py")
    assert not check_domain_literals('FILTER_KEY = "movie_id"\n', "movielab/rag/retriever.py")


def test_tc_nf2005_11_source_files_not_git_ignored():
    import shutil
    import subprocess

    import pytest

    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("Git 저장소가 아니다")
    files = [p.relative_to(ROOT).as_posix() for p in archcheck.python_files()]
    files += [p.relative_to(ROOT).as_posix() for p in (ROOT / "tests").rglob("*.py")]
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", *files],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode in (0, 1), f"git check-ignore 실패: {result.stderr}"
    ignored = result.stdout.split()
    assert ignored == [], f".gitignore에 걸린 소스 파일: {ignored}"


INDEX_TEXT_LABELS = r"^(제목|원제|장르|감독|출연|제작 국가|원어|줄거리): "


def test_tc_f2001_08_index_text_labels_only_in_data():
    checker = archcheck.literal_checker(INDEX_TEXT_LABELS, exempt_data=True)
    violations = archcheck.scan_repo(checker)
    assert violations == [], "\n".join(map(str, violations))
    assert checker('LINE = "감독: 정보 없음"\n', "movielab/rag/x.py")
