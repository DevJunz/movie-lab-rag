"""SSAFY GMS(OpenAI 호환) 채팅 · 임베딩 모델 생성. 키와 주소는 `.env`에서만 온다 (NF2003)."""

from __future__ import annotations

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from movielab.config import Settings
from movielab.core.errors import MissingApiKeyError


def _require_gms(settings: Settings) -> tuple[str, str]:
    secrets = settings.secrets
    if not secrets.has_gms:
        raise MissingApiKeyError("GMS_API_KEY 또는 GMS_BASE_URL이 없다")
    return secrets.gms_api_key, secrets.gms_base_url  # type: ignore[return-value]


def make_chat_model(settings: Settings) -> ChatOpenAI:
    api_key, base_url = _require_gms(settings)
    return ChatOpenAI(
        model=settings.models.chat,
        api_key=api_key,
        base_url=base_url,
        temperature=settings.models.temperature,
        timeout=settings.models.timeout_sec,
    )


def make_embeddings(settings: Settings) -> OpenAIEmbeddings:
    api_key, base_url = _require_gms(settings)
    return OpenAIEmbeddings(
        model=settings.models.embedding,
        api_key=api_key,
        base_url=base_url,
        timeout=settings.models.timeout_sec,
        # 토큰 계산 파일을 외부에서 내려받지 않고, 호환 프록시에 문자열을 그대로 보낸다
        check_embedding_ctx_length=False,
        # 재시도는 색인 정책(A-21)만 따른다 — SDK 자체 재시도를 겹치지 않는다
        max_retries=0,
    )
