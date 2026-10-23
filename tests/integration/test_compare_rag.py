"""SPEC-F2015 TC-02 — 가짜 LLM으로 RAG 전후 비교 보고서를 만든다."""

from __future__ import annotations

import json

import pytest

from movielab.core.types import AnswerResult, CollectReport, Evidence, ItemRecord
from tests.fakes import FakeChatModel


def _questions(tmp_path):
    path = tmp_path / "questions.json"
    path.write_text(
        json.dumps(
            [
                {"id": "Q1", "movie_id": "1", "question": "블랙홀은?", "purpose": "t",
                 "reference_facts": [{"fact": "사건의 지평선", "source_url": "https://ko.wikipedia.org/wiki/x"}]},
                {"id": "Q2", "movie_id": "2", "question": "배는 | 몇 척?", "purpose": "t",
                 "reference_facts": []},
                {"id": "Q3", "movie_id": "999", "question": "없는 영화?", "purpose": "t",
                 "reference_facts": []},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )  # fmt: skip
    return path


class _FakeCatalog:
    def get(self, item_id):
        names = {"1": ("인터스텔라", 2014), "2": ("명량", 2014)}
        if item_id not in names:
            return None
        title, year = names[item_id]
        return ItemRecord(
            item_id=item_id, title=title, year=year, index_text="", metadata={}, url=""
        )


class _FakeQA:
    def __init__(self):
        self.calls = []

    def ask(self, movie_id, question, on_progress=None):
        self.calls.append(movie_id)
        ev = Evidence(
            n=1, chunk_id=f"{movie_id}:w:1:0", source_kind="wiki", source_type="위키백과",
            title="블랙홀", text="t", url="https://ko.wikipedia.org/wiki/x", license="CC BY-SA 4.0",
        )  # fmt: skip
        return AnswerResult(
            answer="RAG 답\n둘째 줄 [근거 1]", evidences=[ev], cited=[ev], uncited=False,
            not_found=False, collect=CollectReport(item_id=movie_id, question=question),
        )  # fmt: skip


def test_tc_f2015_02_compare_rag_report(tmp_settings, tmp_path, monkeypatch):
    from movielab.data.domain_movie import MOVIE_PROFILE
    from movielab.services.baseline import DirectAnswerService
    from scripts import compare_rag

    llm = FakeChatModel(rules={"직접 답변": "직접 답 (출처: 위키백과)"})

    class FakeServices:
        def __init__(self, settings):
            self.settings = settings
            self.llm = llm
            self.qa = _FakeQA()
            self.catalog = _FakeCatalog()
            self.profile = MOVIE_PROFILE
            self.direct = DirectAnswerService(self.catalog, llm, MOVIE_PROFILE)

    services = FakeServices(tmp_settings)
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    monkeypatch.setattr(compare_rag, "build_services", lambda settings: services)
    out = tmp_path / "out.md"
    raw_dir = tmp_path / "raw"
    argv = ["--questions", str(_questions(tmp_path)), "--out", str(out), "--raw-dir", str(raw_dir)]
    out.write_text("옛 보고서", encoding="utf-8")
    argv.append("--force")
    assert compare_rag.main(argv) == 0

    text = out.read_text(encoding="utf-8")
    assert "## 1. 실험 조건" in text
    assert tmp_settings.models.chat in text
    header = (
        "| 질문 | RAG 없음 답변 | RAG 답변 | 인용 수 | 정답 요지 "
        "| 사실 정확성 | 근거 제시 | 모르면 모른다고 답함 |"
    )
    assert header in text
    rows = [line for line in text.splitlines() if line.startswith("| Q")]
    assert [r.split()[1] for r in rows] == ["Q1", "Q2", "Q3"]
    q1, q2, q3 = rows
    assert q1.endswith("|  |  |  |")  # 평가 열 3개는 빈칸
    assert "RAG 답<br>둘째 줄 [근거 1]" in q1 and "| 1 |" in q1 and "사건의 지평선" in q1
    assert "배는 / 몇 척?" in q2
    assert "항목 없음" in q3
    assert services.qa.calls == ["1", "2"]
    prompts = llm.prompts_for("직접 답변")
    assert len(prompts) == 2 and "인터스텔라 (2014)" in prompts[0]
    assert "출처 언급: 있음" in text  # RAG 없는 답변의 출처 언급 자동 보조값
    raw = json.loads(next(raw_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert [r["id"] for r in raw["results"]] == ["Q1", "Q2", "Q3"]


def test_tc_f2015_05_existing_report_not_overwritten(tmp_settings, tmp_path, monkeypatch):
    from scripts import compare_rag

    monkeypatch.setattr(compare_rag, "build_services", lambda settings: pytest.fail("호출 안 됨"))
    out = tmp_path / "out.md"
    out.write_text("사람이 채운 평가", encoding="utf-8")
    argv = ["--questions", str(_questions(tmp_path)), "--out", str(out)]
    assert compare_rag.main(argv) == 1
    assert out.read_text(encoding="utf-8") == "사람이 채운 평가"
