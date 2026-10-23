"""유사도 검색과 MMR 검색의 근거 목록을 나란히 비교한다 (SPEC-F2014 §2.2, V4.5-2).

python -m scripts.compare_retrieval --movie-id 157336 --question "…" [--top-k 4]
결과 표를 출력하고 `<out-dir>/<movie_id>.md`에 덧붙인다. 메타 근거는 두 방식에 같아 뺀다.
"""

from __future__ import annotations

import argparse
import itertools
import logging
import math
import sys
from pathlib import Path

from movielab.config import load_settings
from movielab.container import build_services
from movielab.core import messages
from movielab.core.errors import MovieLabUserError
from movielab.core.types import Evidence
from scripts.index_meta import configure_stdout, integer

logger = logging.getLogger(__name__)

DEFAULT_OUT_DIR = Path("docs/verification/retrieval_compare")


def _cell(evidence: Evidence | None) -> str:
    if evidence is None:
        return "—"
    order = evidence.chunk_id.rsplit(":", 1)[-1]
    score = "—" if evidence.score is None else f"{evidence.score:.3f}"
    return f"{evidence.title} · #{order} · {score}".replace("|", "/")


def _mean_pair_cosine(vectors: list[list[float]]) -> float | None:
    def cos(a: list[float], b: list[float]) -> float:
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(x * x for x in b)) or 1.0
        return sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb)

    pairs = list(itertools.combinations(vectors, 2))
    return sum(cos(a, b) for a, b in pairs) / len(pairs) if pairs else None


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def render_report(
    question: str,
    sim: list[Evidence],
    mmr: list[Evidence],
    embed: object,
    *,
    fetch_k: int,
    lambda_mult: float,
) -> str:
    rows = [
        f"## 질문: {question}",
        "",
        f"외부 근거 Top-{max(len(sim), len(mmr))} · MMR fetch_k={fetch_k}, λ={lambda_mult}",
        "",
        "| 순위 | 유사도 | MMR |",
        "|---|---|---|",
    ]
    for i in range(max(len(sim), len(mmr))):
        left = sim[i] if i < len(sim) else None
        right = mmr[i] if i < len(mmr) else None
        rows.append(f"| {i + 1} | {_cell(left)} | {_cell(right)} |")

    def metrics(items: list[Evidence]) -> tuple[int, float | None]:
        vectors = embed.embed_documents([e.text for e in items]) if len(items) > 1 else []
        return len({e.url or e.title for e in items}), _mean_pair_cosine(vectors)

    sim_docs, sim_cos = metrics(sim)
    mmr_docs, mmr_cos = metrics(mmr)
    overlap = len({e.chunk_id for e in sim} & {e.chunk_id for e in mmr})
    rows += [
        "",
        "| 지표 | 유사도 | MMR |",
        "|---|---|---|",
        f"| 서로 다른 문서 수 | {sim_docs} | {mmr_docs} |",
        f"| 근거 쌍 평균 코사인 유사도 (낮을수록 다양) | {_fmt(sim_cos)} | {_fmt(mmr_cos)} |",
        f"| 두 목록의 겹침 수 | {overlap} | {overlap} |",
        "",
    ]
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="유사도 / MMR 검색 비교")
    parser.add_argument("--movie-id", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--top-k", type=integer, help="외부 근거 수 (기본: 설정)")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)
    configure_stdout()

    labels = None
    try:
        settings = load_settings()
        services = build_services(settings)
        labels = services.profile.labels()
        results = {}
        for kind in ("similarity", "mmr"):
            retriever = services.retriever(top_k=args.top_k, search_type=kind)
            result = retriever.retrieve(args.movie_id, args.question)
            results[kind] = [e for e in result.evidences if e.source_kind != "meta"]
        report = render_report(
            args.question,
            results["similarity"],
            results["mmr"],
            services.embeddings,
            fetch_k=retriever.fetch_k,
            lambda_mult=retriever.lambda_mult,
        )
        print(report)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        path = args.out_dir / f"{args.movie_id}.md"
        header = "" if path.exists() else f"# 유사도 vs MMR 검색 비교 — {args.movie_id}\n\n"
        with path.open("a", encoding="utf-8") as file:
            file.write(header + report + "\n")
        return 0
    except MovieLabUserError as error:
        logger.warning("안내 오류: %s", error)
        print(messages.render(error.code, labels))
    except Exception:
        logger.exception("compare_retrieval 실패")
        print(messages.render("GENERIC_ERROR", labels))
    return 1


if __name__ == "__main__":
    sys.exit(main())
