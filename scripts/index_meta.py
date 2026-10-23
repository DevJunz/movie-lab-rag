"""영화 메타데이터 색인 스크립트 (RAG 1).

    python -m scripts.index_meta --show 157336   # 영화 1편의 색인 텍스트 출력 (SPEC-F2001)

색인 · 건수 · 재색인 옵션은 SPEC-F2002에서 더한다.
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="영화 메타데이터 색인")
    parser.add_argument("--show", metavar="ITEM_ID", help="색인 텍스트를 출력할 항목 ID")
    args = parser.parse_args(argv)
    configure_stdout()

    labels = None
    try:
        services = build_services(load_settings())
        labels = services.profile.labels()
        if args.show:
            return _show(services, args.show)
        parser.print_help()
        return 0
    except MovieLabUserError as error:
        logger.warning("안내 오류: %s", error)
        print(messages.render(error.code, labels))
    except Exception:
        logger.exception("index_meta 실패")
        print(messages.render("GENERIC_ERROR", labels))
    return 1


if __name__ == "__main__":
    sys.exit(main())
