"""영화 메타데이터 색인 스크립트 (RAG 1).

    python -m scripts.index_meta                 # 색인 (재실행해도 중복 없음, SPEC-F2002)
    python -m scripts.index_meta --rebuild       # 컬렉션을 지우고 다시 색인
    python -m scripts.index_meta --count         # 현재 색인 건수 (키 없이 가능)
    python -m scripts.index_meta --show 157336   # 영화 1편의 색인 텍스트 출력 (SPEC-F2001)

사용자 문구는 core/messages에서 가져오고, 예상하지 못한 오류도 traceback 없이 안내한다(NF2004).
"""

from __future__ import annotations

import argparse
import logging
import sys

from movielab.config import load_settings
from movielab.container import build_services
from movielab.core import messages
from movielab.core.errors import MovieLabUserError
from movielab.services.indexing import index_catalog

logger = logging.getLogger(__name__)


def configure_stdout() -> None:
    """Windows 콘솔(cp949)에서도 한국어가 깨지지 않게 한다."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass


def _show(services, item_id: str) -> int:
    item = services.catalog.get(item_id)
    if item is None:
        print(messages.render("ITEM_NOT_FOUND", services.profile.labels(), item_id=item_id))
        return 1
    print(item.index_text)
    return 0


def _count(services) -> int:
    collections = services.settings.collections
    for name in (collections.meta, collections.docs):
        print(f"{name}: {services.store.count(name)}")
    return 0


def positive_int(value: str) -> int:
    """argparse 형식 검사: 1 이상의 정수만 받는다 (0 · 음수는 인자 오류, 종료 코드 2)."""
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"정수가 아닙니다: {value}") from None
    if number < 1:
        raise argparse.ArgumentTypeError(f"1 이상이어야 합니다: {value}")
    return number


def _index(services, rebuild: bool, batch_size: int | None) -> int:
    report = index_catalog(services.catalog, services.store, rebuild=rebuild, batch_size=batch_size)
    print(
        messages.render(
            "INDEX_REPORT",
            loaded=report.loaded,
            indexed=report.indexed,
            skipped=report.skipped,
        )
    )
    if report.removed:
        print(messages.render("INDEX_REMOVED", removed=report.removed))
    if report.failed_batches:
        print(messages.render("INDEX_FAILED_BATCHES", batches=report.failed_batches))
    if not report.ok:
        print(messages.render("INDEX_MISMATCH"))
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="영화 메타데이터 색인")
    parser.add_argument("--show", metavar="ITEM_ID", help="색인 텍스트를 출력할 항목 ID")
    parser.add_argument("--count", action="store_true", help="현재 색인 건수만 출력")
    parser.add_argument("--rebuild", action="store_true", help="컬렉션을 지우고 다시 색인")
    parser.add_argument(
        "--batch-size",
        type=positive_int,
        default=None,
        help="이번 실행의 배치 크기 (기본: settings.json의 indexing.batch_size)",
    )
    args = parser.parse_args(argv)
    configure_stdout()

    labels = None
    try:
        services = build_services(load_settings())
        labels = services.profile.labels()
        if args.show:
            return _show(services, args.show)
        if args.count:
            return _count(services)
        return _index(services, args.rebuild, args.batch_size)
    except MovieLabUserError as error:
        logger.warning("안내 오류: %s", error)
        print(messages.render(error.code, labels))
    except Exception:
        logger.exception("index_meta 실패")
        print(messages.render("GENERIC_ERROR", labels))
    return 1


if __name__ == "__main__":
    sys.exit(main())
