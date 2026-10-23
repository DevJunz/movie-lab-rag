"""프롬프트 첫 줄의 `[작업: …]` 머리표로 작업을 알아보고 정해 둔 답을 돌려주는 가짜 채팅 모델."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

TASK_HEADER = re.compile(r"^\s*\[작업:\s*([^\]]+)\]")

# 규칙 값: 고정 문자열, 프롬프트를 받아 문자열을 돌려주는 함수, 또는 던질 예외
Rule = str | Callable[[str], str] | BaseException


def task_of(prompt: str) -> str | None:
    """프롬프트 첫 줄의 작업 이름. 머리표가 없으면 None."""
    match = TASK_HEADER.match(prompt)
    return match.group(1).strip() if match else None


class FakeChatModel(BaseChatModel):
    """`rules[작업 이름]`으로 답한다. 받은 프롬프트는 `calls`에 (작업, 프롬프트)로 남는다."""

    rules: dict[str, Any] = Field(default_factory=dict)
    default: Any = ""
    calls: list[tuple[str | None, str]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "fake-chat"

    def prompts_for(self, task: str) -> list[str]:
        return [prompt for name, prompt in self.calls if name == task]

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        prompt = "\n".join(str(m.content) for m in messages)
        task = task_of(prompt)
        self.calls.append((task, prompt))
        rule = self.rules.get(task, self.default) if task else self.default
        if isinstance(rule, BaseException):
            raise rule
        text = rule(prompt) if callable(rule) else str(rule)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


def pick_titles(*titles: str) -> Callable[[str], str]:
    """P2 응답 함수: 프롬프트의 후보 줄(`번호. 제목: 요약`)에서 주어진 제목의 번호만 고른다."""
    wanted = set(titles)
    line = re.compile(r"^(\d+)\. (.+?): ", re.MULTILINE)

    def respond(prompt: str) -> str:
        picked = [int(n) for n, title in line.findall(prompt) if title in wanted]
        return str(picked)

    return respond
