"""영화 메타데이터 색인 스크립트 (RAG 1).

    python -m scripts.index_meta --show 157336   # 영화 1편의 색인 텍스트 출력 (SPEC-F2001)

색인 · 건수 · 재색인 옵션은 SPEC-F2002에서 더한다.
"""

from __future__ import annotations

import argparse
import sys

from movielab.config import load_settings
from movielab.container import build_services
from movielab.core.errors import DataNotFoundError

DATA_MISSING_HINT = (
    "항목 데이터 파일을 찾을 수 없습니다. 제공 데이터 팩을 저장소 루트에 두었는지, "
    "config/settings.json의 paths.movies 경로를 확인하세요."
)


def configure_stdout() -> None:
    """Windows 콘솔(cp949)에서도 한국어가 깨지지 않게 한다."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="영화 메타데이터 색인")
    parser.add_argument("--show", metavar="ITEM_ID", help="색인 텍스트를 출력할 항목 ID")
    args = parser.parse_args(argv)
    configure_stdout()

    services = build_services(load_settings())
    try:
        if args.show:
            item = services.catalog.get(args.show)
            if item is None:
                print(f"ID {args.show}인 항목을 찾을 수 없습니다.")
                return 1
            print(item.index_text)
            return 0
    except DataNotFoundError:
        print(DATA_MISSING_HINT)
        return 1
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
