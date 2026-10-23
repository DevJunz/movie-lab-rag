"""CI용 가짜 의존성 (01-architecture.md §10.3). 실제 GMS · 위키백과를 부르지 않는다."""

from tests.fakes.clock import FakeClock
from tests.fakes.domain import BOOK_PROFILE
from tests.fakes.embeddings import FakeEmbeddings
from tests.fakes.http import FakeHttpSession, FakeResponse
from tests.fakes.llm import FakeChatModel, pick_titles, task_of
from tests.fakes.manifest import make_manifest
from tests.fakes.retriever import FakeRetriever

__all__ = [
    "BOOK_PROFILE",
    "FakeChatModel",
    "FakeClock",
    "FakeEmbeddings",
    "FakeHttpSession",
    "FakeResponse",
    "FakeRetriever",
    "pick_titles",
    "make_manifest",
    "task_of",
]
