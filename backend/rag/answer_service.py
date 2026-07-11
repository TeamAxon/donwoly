import logging

from chat.answer_generation import generate_answer
from chat.query_understanding import interpret_query
from rag.qdrant_search import search_chunks

logger = logging.getLogger("uvicorn.error")

MIN_RELEVANCE_SCORE = 0.18
SEARCH_TOP_K = 10
CONTEXT_TOP_K = 5


def _merge_chunks(chunk_groups: list[list[dict]], top_k: int = CONTEXT_TOP_K) -> list[dict]:
    unique: dict[str, dict] = {}
    for chunks in chunk_groups:
        for chunk in chunks:
            chunk_id = str(chunk.get("id"))
            previous = unique.get(chunk_id)
            if previous is None or chunk.get("score", 0) > previous.get("score", 0):
                unique[chunk_id] = chunk
    return sorted(unique.values(), key=lambda item: item.get("score", 0), reverse=True)[:top_k]


def _log_search_debug(
    user_message: str,
    search_query_en: str,
    category: str | None,
    raw_chunks: list[dict],
    selected_chunks: list[dict],
) -> None:
    logger.info(
        "RAG search debug | question_ko=%r | search_query_en=%r | category=%s | raw=%s | selected=%s",
        user_message,
        search_query_en,
        category or "all",
        [
            {
                "title": chunk.get("payload", {}).get("title"),
                "category": chunk.get("payload", {}).get("category"),
                "score": round(float(chunk.get("score", 0)), 4),
            }
            for chunk in raw_chunks[:SEARCH_TOP_K]
        ],
        [
            {
                "title": chunk.get("payload", {}).get("title"),
                "category": chunk.get("payload", {}).get("category"),
                "score": round(float(chunk.get("score", 0)), 4),
            }
            for chunk in selected_chunks
        ],
    )


async def build_rag_answer(
    user_message: str, user_profile: dict, category: str | None
) -> dict:
    """
    1) 질문 해석 후 search_chunks()로 검색
    2) generate_answer()로 답변 생성 + 자체 검증
    3) {"answer": str, "sources": [...]} 형태로 리턴
    """
    interpretation = await interpret_query(user_message, user_profile)
    search_query_en = interpretation["search_query_en"]
    resolved_category = category or interpretation["category"]
    logger.info(
        "RAG translated query | question_ko=%r | search_query_en=%r | category=%s",
        user_message,
        search_query_en,
        resolved_category or "all",
    )

    chunk_groups = [
        search_chunks(
            search_query_en,
            category=resolved_category,
            top_k=SEARCH_TOP_K,
        )
    ]
    raw_chunks = _merge_chunks(chunk_groups, top_k=SEARCH_TOP_K)
    chunks = raw_chunks[:CONTEXT_TOP_K]
    chunks = [
        chunk
        for chunk in chunks
        if chunk.get("score") is None or chunk.get("score", 0) >= MIN_RELEVANCE_SCORE
    ]
    _log_search_debug(
        user_message, search_query_en, resolved_category, raw_chunks, chunks
    )

    result = await generate_answer(
        user_message, chunks, user_profile, resolved_category
    )
    if not result["grounded"]:
        return {"answer": result["answer"], "sources": []}

    sources = [
        {
            "title": chunk["payload"]["title"],
            "source": chunk["payload"].get("source"),
            "category": chunk["payload"].get("category"),
            "score": chunk["score"],
        }
        for chunk in chunks
    ]
    return {"answer": result["answer"], "sources": sources}
