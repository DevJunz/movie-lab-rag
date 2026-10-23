"""대표 질문을 RAG 없이 / RAG로 한 번씩 답하게 하고 나란히 기록한다 (SPEC-F2015 §2.2, V4.6).

python -m scripts.compare_rag [--questions docs/verification/questions.json]
                              [--out docs/deliverables/04_RAG_전후_비교.md]
                              [--raw-dir reports/compare_rag]
평가 열(사실 정확성 · 근거 제시 · 모르면 모른다고 답함)은 빈칸으로 두고 사람이 채운다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from movielab.config import load_settings
from movielab.container import build_services
from movielab.core.logs import configure_from_settings
from scripts.index_meta import configure_stdout

DEFAULT_QUESTIONS = Path("docs/verification/questions.json")
DEFAULT_OUTPUT = Path("docs/deliverables/04_RAG_전후_비교.md")
DEFAULT_RAW_DIR = Path("reports/compare_rag")
MISSING_ITEM = "항목 없음"

# RAG 없는 답변의 출처 언급 — 근거 제시 열의 자동 보조값
_SOURCE_MENTION = re.compile(r"출처|참고|위키|wikipedia|https?://", re.I)


def _cell(text: str) -> str:
    return text.strip().replace("|", "/").replace("\r", "").replace("\n", "<br>")


def _facts(question: dict) -> str:
    facts = question.get("reference_facts") or []
    return "<br>".join(_cell(f"{f['fact']} ({f['source_url']})") for f in facts) or "—"


def run(services, questions: list[dict]) -> list[dict]:
    results = []
    for q in questions:
        item = services.catalog.get(q["movie_id"])
        if item is None:
            results.append({**q, "item": None, "direct": None, "rag": None, "cited": 0})
            continue
        direct = services.direct.ask(q["movie_id"], q["question"])
        rag = services.qa.ask(q["movie_id"], q["question"])
        results.append(
            {
                **q,
                "item": item.display_name,
                "direct": direct,
                "rag": rag.answer,
                "cited": len(rag.cited),
                "cited_urls": [e.url for e in rag.cited],
                "not_found": rag.not_found,
            }
        )
    return results


def render_report(settings, results: list[dict], when: datetime) -> str:
    r = settings.retrieval
    lines = [
        "# RAG 전후 품질 비교 (SPEC-F2015)",
        "",
        "## 1. 실험 조건",
        "",
        f"- 날짜: {when:%Y-%m-%d %H:%M}",
        f"- 모델: {settings.models.chat} · temperature {settings.models.temperature}"
        " (두 조건 같음)",
        f"- 청크: {settings.chunking.chunk_size}자 / 겹침 {settings.chunking.chunk_overlap}자",
        f"- 검색: {r.search_type} · Top-k {r.top_k}",
        "- RAG 없음: 프롬프트 B1(`[작업: 직접 답변]`, 영화 제목 (연도) + 질문, 근거 없음)",
        "- RAG 사용: `QAService.ask` (수집 → 검색 → 근거 답변 → 인용 정리)",
        "",
        "## 2. 질문별 비교",
        "",
        "평가 열은 사람이 `reference_facts` 기준으로 채운다. "
        "사실 정확성(정확 / 부분 / 틀림), 근거 제시(있음 / 없음), "
        "모르면 모른다고 답함(예 / 아니오 / 해당 없음).",
        "",
        "| 질문 | RAG 없음 답변 | RAG 답변 | 인용 수 | 정답 요지 "
        "| 사실 정확성 | 근거 제시 | 모르면 모른다고 답함 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for q in results:
        head = f"{q['id']} {_cell(q['question'])}"
        if q["item"] is None:
            lines.append(f"| {head} | {MISSING_ITEM} | {MISSING_ITEM} | — | {_facts(q)} |  |  |  |")
            continue
        mention = "있음" if _SOURCE_MENTION.search(q["direct"]) else "없음"
        direct = f"{_cell(q['direct'])}<br>(출처 언급: {mention})"
        lines.append(
            f"| {head} | {direct} | {_cell(q['rag'])} | {q['cited']} | {_facts(q)} |  |  |  |"
        )
    lines += [
        "",
        "## 3. 요약",
        "",
        "- 기준별 집계: (평가 기입 후 작성)",
        "- 관찰: (환각 사례, 확인 불가 응답)",
        "- 한계: (평가 기입 후 작성)",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RAG 전후 답변 비교")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    args = parser.parse_args(argv)
    configure_stdout()

    settings = load_settings()
    configure_from_settings(settings)
    services = build_services(settings)
    questions = json.loads(args.questions.read_text(encoding="utf-8"))
    results = run(services, questions)
    when = datetime.now()

    args.raw_dir.mkdir(parents=True, exist_ok=True)
    raw = {"date": when.isoformat(timespec="seconds"), "model": settings.models.chat,
           "temperature": settings.models.temperature, "results": results}  # fmt: skip
    (args.raw_dir / f"{when:%Y%m%d-%H%M%S}.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_report(settings, results, when), encoding="utf-8")
    print(f"{len(results)}개 질문 비교 → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
