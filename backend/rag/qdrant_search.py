import os
from functools import lru_cache

from openai import OpenAI, OpenAIError
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from chat.openai_client import AIServiceError


COLLECTION_NAME = "first_month_guide"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_SIZE = 1536
VALID_CATEGORIES = {"visa", "departure", "labor_law", "tax", "life"}


class QdrantSearchError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise AIServiceError("OPENAI_API_KEY environment variable is required")
    return OpenAI(api_key=api_key)


@lru_cache(maxsize=1)
def _get_qdrant_client() -> QdrantClient:
    qdrant_url = os.getenv("QDRANT_URL")
    if not qdrant_url:
        raise QdrantSearchError("QDRANT_URL environment variable is required")
    return QdrantClient(url=qdrant_url, check_compatibility=False)


def embed_query(text: str) -> list[float]:
    if not text.strip():
        raise ValueError("embedding text must not be blank")
    try:
        response = _get_openai_client().embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
        )
    except OpenAIError as exc:
        reason = "ai_service_unavailable"
        if getattr(exc, "code", None) == "insufficient_quota" or getattr(
            exc, "status_code", None
        ) == 429:
            reason = "openai_insufficient_quota"
        raise AIServiceError("OpenAI embedding request failed", reason=reason) from exc

    embedding = response.data[0].embedding
    if len(embedding) != EMBEDDING_SIZE:
        raise AIServiceError(
            f"Unexpected embedding size: expected {EMBEDDING_SIZE}, got {len(embedding)}"
        )
    return embedding


def search_chunks(
    query: str, category: str | None = None, top_k: int = 5
) -> list[dict]:
    """
    query를 임베딩해서 Qdrant 컬렉션(first_month_guide)에서 코사인 유사도 검색.
    category가 있으면 payload.category 필터 적용.
    반환: 확정 payload 스키마 리스트 (score 포함).
    """
    if top_k < 1:
        raise ValueError("top_k must be at least 1")
    if category == "labor":
        category = "labor_law"

    if category is not None and category not in VALID_CATEGORIES:
        raise ValueError(f"unsupported category: {category}")

    query_vector = embed_query(query)
    query_filter = None
    if category:
        query_filter = Filter(
            must=[FieldCondition(key="category", match=MatchValue(value=category))]
        )

    try:
        response = _get_qdrant_client().query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )
    except Exception as exc:
        raise QdrantSearchError("Qdrant search request failed") from exc

    return [
        {
            "id": point.id,
            "score": point.score,
            "payload": dict(point.payload or {}),
        }
        for point in response.points
    ]
