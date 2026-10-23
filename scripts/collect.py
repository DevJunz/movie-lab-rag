"""영화 1편 · 질문 1개에 대한 외부 문서 수집 (SPEC-F2004).

    python -m scripts.collect --movie-id 157336 --question "블랙홀 묘사는 실제와 얼마나 다른가?"
    python -m scripts.collect --movie-id 157336 --question "…" --source bundle

검색어(V4.2-1), 색인 · 버린 문서와 사유(V4.2-2), 항목 자체 문서(V4.2-4)를 출력한다.
청크 색인(F2005)과 수집 캐시(NF2002)는 해당 SPEC에서 연결된다.
"""

from __future__ import annotations

import argparse
import logging
import sys

from movielab.config import load_settings
from movielab.container import build_services
from movielab.core import messages
from movielab.core.errors import MovieLabUserError
from scripts.index_meta import configure_stdout, positive_int

logger = logging.getLogger(__name__)


def _print_report(report) -> None:
    print(f"소스: {report.source_used}")
    print(f"검색어: {', '.join(report.queries)}")
    if report.cached_queries:
        print(f"캐시에 있어 건너뛴 검색어: {', '.join(report.cached_queries)}")
    print(f"후보: {len(report.candidates)}건")
    print("수집 문서:")
    for title in report.indexed_titles:
        mark = " (항목 자체 문서)" if title == report.item_doc_title else ""
        print(f"  - {title}{mark}")
    print("버린 문서:")
    for rejection in report.rejected:
        print(f"  - {rejection.title} [{rejection.reason}]")
    if report.notices:
        print(f"안내 코드: {', '.join(report.notices)}")


def _print_evidence(result) -> None:
    """근거 목록 (SPEC-F2006 V4.3-1): 번호 · 출처 유형 · 제목 · 점수."""
    print(messages.EVIDENCE_LIST_HEADER)
    for evidence in result.evidences:
        score = (
            ""
            if evidence.score is None
            else messages.EVIDENCE_LIST_SCORE.format(score=evidence.score)
        )
        print(
            messages.EVIDENCE_LIST_LINE.format(
                n=evidence.n, source_type=evidence.source_type, title=evidence.title, score=score
            )
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="외부 문서 수집")
    parser.add_argument("--movie-id", help="항목 ID")
    parser.add_argument("--question", help="질문")
    parser.add_argument(
        "--reset-cache",
        action="store_true",
        help="수집 캐시를 지운다 (--movie-id가 있으면 그 영화만)",
    )
    parser.add_argument(
        "--source", choices=["api", "bundle", "auto"], help="수집 소스 (기본: 설정)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="색인 · 캐시 기록 없이 수집 결과만 확인"
    )
    parser.add_argument("--show-evidence", action="store_true", help="수집 뒤 근거 목록 출력")
    parser.add_argument("--top-k", type=positive_int, help="근거 검색 수 (이번 실행만)")
    args = parser.parse_args(argv)
    if not args.reset_cache and not (args.movie_id and args.question):
        parser.error("--movie-id와 --question이 필요합니다 (또는 --reset-cache)")
    if args.top_k is not None and not args.show_evidence:
        parser.error("--top-k는 --show-evidence와 함께 씁니다")
    if args.dry_run and args.show_evidence:
        parser.error("--dry-run은 색인하지 않으므로 --show-evidence와 함께 쓸 수 없습니다")
    configure_stdout()

    labels = None
    try:
        settings = load_settings()
        if args.source:
            settings.raw["collect"]["source"] = args.source
        services = build_services(settings)
        labels = services.profile.labels()
        if args.reset_cache:
            if not services.manifest.reset(args.movie_id):
                print(messages.render("CACHE_RESET_FAILED", labels))
                return 1
            if args.movie_id:
                print(messages.render("CACHE_RESET", labels, target=args.movie_id))
            else:
                print(messages.render("CACHE_RESET_ALL", labels))
            return 0
        item = services.catalog.get(args.movie_id)
        if item is None:
            print(messages.render("ITEM_NOT_FOUND", labels, item_id=args.movie_id))
            return 1
        retriever = services.retriever(top_k=args.top_k) if args.show_evidence else None
        if retriever is not None:
            retriever.check(item.item_id)  # 색인이 비었으면 수집 전에 안내하고 끝낸다
        collector = services.make_collector(dry_run=args.dry_run)
        _print_report(collector.collect(item, args.question))
        if retriever is not None:
            _print_evidence(retriever.retrieve(item.item_id, args.question))
        return 0
    except MovieLabUserError as error:
        logger.warning("안내 오류: %s", error)
        print(messages.render(error.code, labels))
    except Exception:
        logger.exception("collect 실패")
        print(messages.render("GENERIC_ERROR", labels))
    return 1


if __name__ == "__main__":
    sys.exit(main())
