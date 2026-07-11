import logging

from chat.answer_generation import generate_answer
from chat.query_understanding import interpret_query
from rag.qdrant_search import search_chunks

logger = logging.getLogger(__name__)

MIN_RELEVANCE_SCORE = 0.18
SEARCH_TOP_K = 10
CONTEXT_TOP_K = 5

QUERY_EXPANSION_KEYWORDS = {
    "신원": [
        "character requirement",
        "신원 요건",
        "범죄경력",
        "police certificate",
        "character documents",
        "호주 내무부",
    ],
    "character": [
        "character requirement",
        "신원 요건",
        "범죄경력",
        "police certificate",
        "character documents",
    ],
    "범죄": [
        "character requirement",
        "신원 요건",
        "범죄경력",
        "police certificate",
        "character documents",
    ],
    "건강": [
        "health requirement",
        "건강 요건",
        "health examination",
        "medical examination",
        "호주 내무부",
    ],
    "tfn": ["Tax File Number", "세금 파일 번호", "ATO", "TFN declaration"],
    "세금파일번호": ["TFN", "Tax File Number", "세금 파일 번호", "ATO"],
    "최저임금": ["minimum wage", "award wage", "Fair Work", "casual loading"],
    "임금": ["pay and wages", "minimum wage", "award wage", "Fair Work"],
    "연금": ["superannuation", "super", "퇴직연금", "ATO"],
    "응급": ["emergency", "000", "Police Fire Ambulance", "영사콜센터"],
}


def _expand_search_query(user_message: str, search_query: str) -> str:
    joined = f"{user_message} {search_query}".lower().replace(" ", "")
    expansions: list[str] = []
    for trigger, keywords in QUERY_EXPANSION_KEYWORDS.items():
        if trigger.lower().replace(" ", "") in joined:
            expansions.extend(keywords)

    if not expansions:
        return search_query
    unique_expansions = list(dict.fromkeys(expansions))
    return f"{search_query} {' '.join(unique_expansions)}"


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
    search_query: str,
    categories: list[str],
    raw_chunks: list[dict],
    selected_chunks: list[dict],
) -> None:
    logger.info(
        "RAG search debug | question=%r | search_query=%r | categories=%s | raw=%s | selected=%s",
        user_message,
        search_query,
        categories or ["all"],
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
    search_query = _expand_search_query(user_message, interpretation["search_query"])
    categories = [category] if category else interpretation["categories"]

    if categories:
        chunk_groups = [
            search_chunks(search_query, category=item, top_k=SEARCH_TOP_K)
            for item in categories
        ]
    else:
        chunk_groups = [search_chunks(search_query, category=None, top_k=SEARCH_TOP_K)]
    raw_chunks = _merge_chunks(chunk_groups, top_k=SEARCH_TOP_K)
    chunks = raw_chunks[:CONTEXT_TOP_K]
    chunks = [
        chunk
        for chunk in chunks
        if chunk.get("score") is None or chunk.get("score", 0) >= MIN_RELEVANCE_SCORE
    ]
    _log_search_debug(user_message, search_query, categories, raw_chunks, chunks)

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
