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


# P2 후보 선별 (SPEC-F2004 §3.6) — 본문을 받기 전에 제목 · 요약만 보고 고른다
CANDIDATE_SELECTION = """[작업: 후보 선별]
너는 자료 조사원이다. {item_label} '{item_name}'에 대한 질문에 답하는 데 도움이 될 문서를 고른다.
질문: {question}

후보 (번호. 제목: 요약):
{candidate_lines}

규칙:
- 질문에 답하는 데 직접 도움이 되는 문서만 고른다. 최대 {max_selected}개.
- 제목이 같아도 다른 대상(음반, 동명 인물 등)을 다룬 문서는 고르지 않는다.
- 출력은 고른 번호의 JSON 정수 배열 하나만. 고를 것이 없으면 []."""


def build_selection_prompt(
    profile: DomainProfile,
    *,
    item_name: str,
    question: str,
    candidate_lines: str,
    max_selected: int,
) -> str:
    return profile.render(
        CANDIDATE_SELECTION,
        item_name=item_name,
        question=question,
        candidate_lines=candidate_lines,
        max_selected=max_selected,
    )
