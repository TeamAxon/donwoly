from chat.answer_generation import generate_answer
from chat.query_understanding import interpret_query
from rag.qdrant_search import search_chunks

MIN_RELEVANCE_SCORE = 0.25


def _merge_chunks(chunk_groups: list[list[dict]], top_k: int = 5) -> list[dict]:
    unique: dict[str, dict] = {}
    for chunks in chunk_groups:
        for chunk in chunks:
            chunk_id = str(chunk.get("id"))
            previous = unique.get(chunk_id)
            if previous is None or chunk.get("score", 0) > previous.get("score", 0):
                unique[chunk_id] = chunk
    return sorted(unique.values(), key=lambda item: item.get("score", 0), reverse=True)[:top_k]


async def build_rag_answer(
    user_message: str, user_profile: dict, category: str | None
) -> dict:
    """
    1) 질문 해석 후 search_chunks()로 검색
    2) generate_answer()로 답변 생성 + 자체 검증
    3) {"answer": str, "sources": [...]} 형태로 리턴
    """
    interpretation = await interpret_query(user_message, user_profile)
    search_query = interpretation["search_query"]
    categories = [category] if category else interpretation["categories"]

    if categories:
        chunk_groups = [
            search_chunks(search_query, category=item, top_k=5) for item in categories
        ]
    else:
        chunk_groups = [search_chunks(search_query, category=None, top_k=5)]
    chunks = _merge_chunks(chunk_groups, top_k=5)
    chunks = [
        chunk
        for chunk in chunks
        if chunk.get("score") is None or chunk.get("score", 0) >= MIN_RELEVANCE_SCORE
    ]

    resolved_category = category or ",".join(categories) or None
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
