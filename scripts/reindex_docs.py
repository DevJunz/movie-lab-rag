"""저장된 원문으로 외부 문서 컬렉션을 다시 색인한다 — 외부 호출 없음 (SPEC-F2005 §3.3).

python -m scripts.reindex_docs                                   # 설정 값으로
python -m scripts.reindex_docs --chunk-size 500 --chunk-overlap 100   # 이번만 바꿔 비교 (V4.2-5)
python -m scripts.reindex_docs --movie-id 157336                 # 한 영화만
"""

from __future__ import annotations

import argparse
import logging
import sys

from movielab.config import load_settings
from movielab.container import build_services
from movielab.core import messages
from movielab.core.errors import MovieLabUserError
from movielab.services.indexing import reindex_documents
from scripts.index_meta import configure_stdout, positive_int

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="외부 문서 재색인")
    parser.add_argument("--movie-id", help="이 항목의 문서만")
    parser.add_argument("--chunk-size", type=positive_int, help="이번 실행의 청크 크기")
    parser.add_argument("--chunk-overlap", type=int, help="이번 실행의 청크 중복")
    args = parser.parse_args(argv)
    configure_stdout()

    labels = None
    try:
        services = build_services(load_settings())
        labels = services.profile.labels()
        documents = services.raw_store.iter_documents()
        if args.movie_id:
            documents = [d for d in documents if d.movie_id == args.movie_id]
        if not documents:
            print(messages.render("REINDEX_EMPTY", labels))
            return 1
        overrides = {}
        if args.chunk_size is not None:
            overrides["chunk_size"] = args.chunk_size
        if args.chunk_overlap is not None:
            overrides["chunk_overlap"] = args.chunk_overlap
        indexer = services.doc_indexer(**overrides)
        count, chunks = reindex_documents(documents, indexer)
        print(
            messages.render(
                "REINDEX_REPORT",
                chunk_size=indexer.chunk_size,
                chunk_overlap=indexer.chunk_overlap,
                documents=count,
                chunks=chunks,
            )
        )
        return 0
    except MovieLabUserError as error:
        logger.warning("안내 오류: %s", error)
        print(messages.render(error.code, labels))
    except ValueError as error:  # 겹침이 크기 이상인 인자 조합 등
        print(str(error))
    except Exception:
        logger.exception("reindex_docs 실패")
        print(messages.render("GENERIC_ERROR", labels))
    return 1


if __name__ == "__main__":
    sys.exit(main())
