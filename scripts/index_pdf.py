"""PDF 문서를 색인한다 (SPEC-F2016 §2.2). PDF는 검색 API가 없으므로 사전 지정 파일을 일괄 색인한다.

python -m scripts.index_pdf     # data/pdf/pdf_manifest.json의 PDF를 모두 색인
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


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="PDF 문서 색인").parse_args(argv)
    configure_stdout()
    labels = None
    manifest = None
    try:
        settings = load_settings()
        manifest = settings.path("pdf_manifest")
        services = build_services(settings)
        labels = services.profile.labels()
        reports = services.index_pdfs()
    except FileNotFoundError:
        logger.warning("PDF 매니페스트 없음: %s", manifest)
        print(messages.render("PDF_MANIFEST_MISSING", labels, path=manifest))
        return 1
    except MovieLabUserError as error:
        logger.warning("안내 오류: %s", error)
        print(messages.render(error.code, labels))
        return 1
    except ValueError:
        logger.exception("PDF 매니페스트 형식 오류")
        print(messages.render("PDF_MANIFEST_INVALID", labels, path=manifest))
        return 1
    except Exception:
        logger.exception("index_pdf 실패")
        print(messages.render("GENERIC_ERROR", labels))
        return 1

    for report in reports:
        if report.missing:
            print(messages.render("PDF_FILE_MISSING", labels, file=report.file))
            continue
        skipped = ", ".join(str(n) for n in report.skipped_pages) or "-"
        print(
            messages.render(
                "PDF_REPORT",
                labels,
                file=report.file,
                pages=report.pages,
                chunks=report.chunks,
                skipped=skipped,
            )
        )
    indexed = [r for r in reports if not r.missing]
    print(
        messages.render(
            "PDF_TOTAL",
            labels,
            documents=len(indexed),
            chunks=sum(r.chunks for r in indexed),
            total=services.store.count(settings.collections.pdf),
        )
    )
    return 0 if len(indexed) == len(reports) else 1


if __name__ == "__main__":
    sys.exit(main())
