"""저장된 원문으로 외부 문서 컬렉션을 다시 색인한다 — 외부 호출 없음 (SPEC-F2005 §3.3).

python -m scripts.reindex_docs                                   # 설정 값으로
python -m scripts.reindex_docs --chunk-size 500 --chunk-overlap 100   # 이번만 바꿔 비교 (V4.2-5)
python -m scripts.reindex_docs --movie-id 157336                 # 한 영화만
"""

from __future__ import annotations

import argparse
import logging
import sys

from movielab.config import chunking_ok, load_settings
from movielab.container import build_services
from movielab.core import messages
from movielab.core.errors import MovieLabUserError
from movielab.core.logs import configure_from_settings
from movielab.services.indexing import reindex_documents
from scripts.index_meta import configure_stdout, integer

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="외부 문서 재색인")
    parser.add_argument("--movie-id", help="이 항목의 문서만")
    parser.add_argument("--chunk-size", type=integer, help="이번 실행의 청크 크기")
    parser.add_argument("--chunk-overlap", type=integer, help="이번 실행의 청크 중복")
    args = parser.parse_args(argv)
    configure_stdout()

    labels = None
    try:
        settings = load_settings()
        configure_from_settings(settings)
        chunking = settings.chunking
        size = chunking.chunk_size if args.chunk_size is None else args.chunk_size
        overlap = chunking.chunk_overlap if args.chunk_overlap is None else args.chunk_overlap
        if not chunking_ok(size, overlap):  # 설정 파일과 같은 규칙 (AC-F2005-10)
            parser.error(
                messages.render("REINDEX_BAD_CHUNKING", chunk_size=size, chunk_overlap=overlap)
            )
        services = build_services(settings)
        labels = services.profile.labels()
        movie_id = args.movie_id or None  # 빈 값은 주지 않은 것과 같다 (재색인 · 정리 범위 일치)
        documents, unreadable = services.raw_store.scan(movie_id=movie_id)
        indexer = services.doc_indexer(chunk_size=size, chunk_overlap=overlap)
        if not documents and not unreadable and not indexer.has_pages(movie_id):
            print(messages.render("REINDEX_EMPTY", labels))
            return 1
        # 원문이 0건이어도 색인된 문서가 있으면 정리한다 (AC-F2005-12)
        report = reindex_documents(
            documents,
            indexer,
            movie_id=movie_id,
            manifest=services.manifest,
            unreadable=unreadable,
        )
        print(
            messages.render(
                "REINDEX_REPORT",
                chunk_size=indexer.chunk_size,
                chunk_overlap=indexer.chunk_overlap,
                documents=report.documents,
                chunks=report.chunks,
                total_chunks=report.total_chunks,
            )
        )
        if report.removed:
            print(messages.render("REINDEX_REMOVED", removed=report.removed))
        if (size, overlap) != (chunking.chunk_size, chunking.chunk_overlap):
            print(messages.render("REINDEX_OVERRIDE_NOTICE"))
        if report.failed:
            print(messages.render("REINDEX_FAILED", failed=report.failed))
            return 1
        return 0
    except MovieLabUserError as error:
        logger.warning("안내 오류: %s", error)
        print(messages.render(error.code, labels))
    except Exception:
        logger.exception("reindex_docs 실패")
        print(messages.render("GENERIC_ERROR", labels))
    return 1


if __name__ == "__main__":
    sys.exit(main())
