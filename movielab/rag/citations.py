"""답변 본문의 `[근거 n]` 표기를 찾아 실제로 인용된 근거만 고른다 (SPEC-F2008).

인식하는 표기: `[근거 3]`, `[근거3]`, `[근거 1, 3]`, `[근거 1][근거 3]`.
번호는 다시 매기지 않는다 — 본문 표기와 근거 목록의 번호가 같아야 한다.
"""

from __future__ import annotations

import logging
import re

from movielab.core.types import CitedResult, Evidence

logger = logging.getLogger(__name__)

_CITATION = re.compile(r"\[근거\s*(\d[^\]]*)\]")
_NUMBER = re.compile(r"(\d+)\s*~\s*(\d+)|(\d+)")


def extract_citations(answer: str, count: int | None = None) -> list[int]:
    """인용된 번호 — 중복 없이 처음 나온 순서. `count`를 주면 `1..count` 밖 번호는 버린다."""
    numbers: list[int] = []
    for match in _CITATION.finditer(answer):
        found: list[int] = []
        for low, high, single in _NUMBER.findall(match.group(1)):
            found += list(range(int(low), int(high) + 1)) if low else [int(single)]
        for number in found:
            if count is not None and not 1 <= number <= count:
                logger.warning("범위 밖 근거 번호를 무시한다: %d (근거 %d개)", number, count)
                continue
            if number not in numbers:
                numbers.append(number)
    return numbers


def select_cited(answer: str, evidences: list[Evidence]) -> CitedResult:
    """인용된 근거만 번호 오름차순으로. 인용이 없으면 `uncited`."""
    by_number = {e.n: e for e in evidences}
    numbers = extract_citations(answer)
    for number in numbers:
        if number not in by_number:
            logger.warning("범위 밖 근거 번호를 무시한다: %d", number)
    cited = [by_number[n] for n in sorted(numbers) if n in by_number]
    return CitedResult(cited=cited, uncited=not cited)
