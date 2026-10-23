"""대표 질문의 응답 시간을 잰다 (SPEC-NF2001 V4.7-1) — 실제 GMS · 위키백과를 쓰므로 로컬에서만.

python -m scripts.measure_latency [--questions docs/verification/questions.json] [--runs 3]
                                  [--output docs/verification/latency.md]

각 질문(Q1~Q5)을 처음(그 영화의 수집 캐시를 비움) 1회 + 캐시 적중 `runs`회 실행해
단계별 시간을 표로 만들고 목표(`settings.latency`, A-10)와 비교한다.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

from movielab.config import load_settings
from movielab.container import build_services
from movielab.core.logs import configure_from_settings
from scripts.index_meta import configure_stdout, positive_int

STEPS = ("collect", "retrieve", "generate", "total")
DEFAULT_QUESTIONS = Path("docs/verification/questions.json")
DEFAULT_OUTPUT = Path("docs/verification/latency.md")


def _row(label: str, kind: str, timings: dict[str, float]) -> str:
    cells = " | ".join(f"{timings.get(step, 0.0):.1f}" for step in STEPS)
    return f"| {label} | {kind} | {cells} |"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="대표 질문 응답 시간 측정")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--runs", type=positive_int, default=3, help="캐시 적중 반복 횟수")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    configure_stdout()

    settings = load_settings()
    configure_from_settings(settings)
    services = build_services(settings)
    targets = settings.latency
    questions = [
        q
        for q in json.loads(args.questions.read_text(encoding="utf-8"))
        if q["id"] != "Q6"  # 확인 불가 검증용 — 측정하지 않는다
    ]
    lines = [
        f"# 응답 시간 측정 (SPEC-NF2001, {datetime.now():%Y-%m-%d %H:%M})",
        "",
        f"캐시 적중은 {args.runs}회의 중앙값. 단위: 초.",
        "",
        "| 질문 | 경우 | " + " | ".join(STEPS) + " |",
        "|---|---|" + "---|" * len(STEPS),
    ]
    firsts: list[float] = []
    cached_totals: list[float] = []
    for q in questions:
        services.manifest.reset(q["movie_id"])  # 처음 묻는 상황
        first = services.qa.ask(q["movie_id"], q["question"]).timings
        runs = [services.qa.ask(q["movie_id"], q["question"]).timings for _ in range(args.runs)]
        cached = {step: statistics.median(r.get(step, 0.0) for r in runs) for step in STEPS}
        firsts.append(first.get("total", 0.0))
        cached_totals.append(cached["total"])
        lines.append(_row(q["id"], "처음", first))
        lines.append(_row(q["id"], "캐시 적중", cached))
        print(f"{q['id']}: 처음 {first.get('total', 0.0):.1f}초 / 캐시 {cached['total']:.1f}초")

    first_median = statistics.median(firsts) if firsts else 0.0
    cached_median = statistics.median(cached_totals) if cached_totals else 0.0

    def verdict(value: float, target: float) -> str:
        return "통과" if value <= target else "초과 — 원인과 개선안을 설계문서에 기록"

    lines += [
        "",
        "| 경우 | 중앙값 | 목표 | 판정 |",
        "|---|---|---|---|",
        f"| 처음 묻는 질문 | {first_median:.1f} | {targets.first_target_sec} | "
        f"{verdict(first_median, targets.first_target_sec)} |",
        f"| 캐시 적중 | {cached_median:.1f} | {targets.cached_target_sec} | "
        f"{verdict(cached_median, targets.cached_target_sec)} |",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"저장: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
