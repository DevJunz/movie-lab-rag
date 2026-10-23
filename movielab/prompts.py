"""프롬프트 템플릿 (01-architecture §7). 도메인 문구는 DomainProfile에서 주입한다.

모든 프롬프트는 첫 줄에 `[작업: …]` 머리표를 둔다 — 로그를 읽기 쉽게 하고,
테스트용 가짜 LLM이 작업 종류를 알아보게 한다.
"""

from __future__ import annotations

from movielab.core.domain import DomainProfile

# P1 검색어 추출 (SPEC-F2003)
QUERY_EXTRACTION = """[작업: 검색어 추출]
너는 {expert_role}이다.
아래 {item_label}과 질문에 답하려면 한국어 위키백과에서 어떤 문서를 찾아봐야 하는지 정하라.

{item_label}: {item_card}
질문: {question}

규칙:
- 위키백과 문서 제목이 될 만한 짧은 명사구로 {min_queries}~{max_queries}개를 고른다.
- 질문에 나온 인물 · 사건 · 개념 · 장소를 우선한다.
- 출력은 JSON 문자열 배열 하나만. 설명을 붙이지 않는다.
예: ["블랙홀", "웜홀", "일반 상대성 이론"]"""


def build_query_prompt(
    profile: DomainProfile, *, item_card: str, question: str, min_queries: int, max_queries: int
) -> str:
    return profile.render(
        QUERY_EXTRACTION,
        item_card=item_card,
        question=question,
        min_queries=min_queries,
        max_queries=max_queries,
    )
