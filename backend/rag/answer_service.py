import logging

from chat.answer_generation import generate_answer
from chat.query_understanding import interpret_query
from rag.qdrant_search import search_chunks
from rag.search_strategies import rerank_chunks_for_strategy, select_search_strategy

logger = logging.getLogger("uvicorn.error")

MIN_RELEVANCE_SCORE = 0.18
SEARCH_TOP_K = 10
CONTEXT_TOP_K = 5

def _format_conversation_history(
    conversation_history: list[dict[str, str]] | None,
    *,
    limit: int = 8,
    max_chars_per_message: int = 500,
) -> str:
    if not conversation_history:
        return ""

    lines: list[str] = []
    for message in conversation_history[-limit:]:
        role = "사용자" if message.get("role") == "user" else "Donwoly"
        content = (message.get("content") or "").strip()
        if not content:
            continue
        if len(content) > max_chars_per_message:
            content = f"{content[:max_chars_per_message]}..."
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _build_contextual_query(
    user_message: str, conversation_history: list[dict[str, str]] | None
) -> str:
    formatted_history = _format_conversation_history(conversation_history)
    if not formatted_history:
        return user_message
    return (
        "아래는 같은 대화방에서 이어진 이전 대화입니다. "
        "현재 질문의 생략된 대상이나 '그거', '그럼' 같은 표현을 이해하는 데만 참고하세요.\n\n"
        f"[이전 대화]\n{formatted_history}\n\n"
        f"[현재 질문]\n{user_message}"
    )


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
    user_message: str,
    user_profile: dict,
    category: str | None,
    conversation_history: list[dict[str, str]] | None = None,
) -> dict:
    """
    1) 질문 해석 후 search_chunks()로 검색
    2) generate_answer()로 답변 생성 + 자체 검증
    3) {"answer": str, "sources": [...]} 형태로 리턴
    """
    contextual_query = _build_contextual_query(user_message, conversation_history)
    interpretation = await interpret_query(contextual_query, user_profile)
    search_query_en = interpretation["search_query_en"]
    resolved_category = category or interpretation["category"]
    intent = interpretation.get("intent")
    strategy = select_search_strategy(
        intent=intent,
        user_message=contextual_query,
        search_query=search_query_en,
    )
    logger.info(
        "RAG translated query | question_ko=%r | search_query_en=%r | category=%s | intent=%s | strategy=%s",
        user_message,
        search_query_en,
        resolved_category or "all",
        intent or "none",
        strategy.intent if strategy else "default",
    )

    if strategy:
        strategy_category = strategy.category
        chunk_groups = []

        for priority_query in strategy.priority_queries:
            chunk_groups.append(
                search_chunks(
                    priority_query,
                    category=strategy_category,
                    top_k=strategy.priority_top_k,
                )
            )
            chunk_groups.append(
                search_chunks(
                    f"{search_query_en} {priority_query}",
                    category=strategy_category,
                    top_k=strategy.priority_top_k,
                )
            )

        chunk_groups.append(
            search_chunks(
                contextual_query,
                category=strategy_category,
                top_k=SEARCH_TOP_K,
            )
        )

        # 명시 카테고리가 전략 카테고리와 다르면 보조 검색만 추가한다.
        if resolved_category and resolved_category != strategy_category:
            chunk_groups.append(
                search_chunks(
                    search_query_en,
                    category=resolved_category,
                    top_k=SEARCH_TOP_K,
                )
            )

        resolved_category = strategy_category
        raw_chunks = rerank_chunks_for_strategy(
            _merge_chunks(chunk_groups, top_k=30),
            strategy,
        )[:SEARCH_TOP_K]
    else:
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
        user_message,
        chunks,
        user_profile,
        resolved_category,
        conversation_history=conversation_history,
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
