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
from scripts.index_meta import configure_stdout

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="외부 문서 수집")
    parser.add_argument("--movie-id", required=True, help="항목 ID")
    parser.add_argument("--question", required=True, help="질문")
    parser.add_argument(
        "--source", choices=["api", "bundle", "auto"], help="수집 소스 (기본: 설정)"
    )
    args = parser.parse_args(argv)
    configure_stdout()

    labels = None
    try:
        settings = load_settings()
        if args.source:
            settings.raw["collect"]["source"] = args.source
        services = build_services(settings)
        labels = services.profile.labels()
        item = services.catalog.get(args.movie_id)
        if item is None:
            print(messages.render("ITEM_NOT_FOUND", labels, item_id=args.movie_id))
            return 1
        _print_report(services.collector.collect(item, args.question))
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
