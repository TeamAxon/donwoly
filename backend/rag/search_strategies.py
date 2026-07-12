from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchStrategy:
    """Intent-specific search rules for RAG retrieval.

    category limits Qdrant search to the best payload category.
    priority_queries add official-document terms that users rarely type.
    boost/downrank keywords adjust results after vector search.
    """

    intent: str
    category: str
    priority_queries: tuple[str, ...]
    trigger_keywords: tuple[str, ...] = ()
    boost_keywords: tuple[str, ...] = ()
    downrank_keywords: tuple[str, ...] = ()
    priority_top_k: int = 30


SEARCH_STRATEGIES: dict[str, SearchStrategy] = {
    "minimum_wage": SearchStrategy(
        intent="minimum_wage",
        category="labor_law",
        priority_queries=(
            "Fair Work Ombudsman current minimum wage pay rates National Minimum Wage casual employee award wage",
            "Fair Work Ombudsman pay guide current minimum wages working holiday maker",
        ),
        trigger_keywords=(
            "최저시급",
            "최저 임금",
            "최저임금",
            "시급",
            "임금",
            "급여",
            "pay rate",
            "minimum wage",
            "wage",
        ),
        boost_keywords=(
            "fair work",
            "ombudsman",
            "minimum wage",
            "pay rates",
            "current",
            "2026",
            "2025",
        ),
        downrank_keywords=("decision", "2021", "2020", "2019"),
    ),
    "safety_area": SearchStrategy(
        intent="safety_area",
        category="life",
        priority_queries=(
            "호주 주요 도시별 우범지역 시드니 Kings Cross Central Redfern 브리즈번 Fortitude Valley Runcorn Sunnybank Hills 퍼스 Northbridge",
            "Australia WHIC crime-prone areas unsafe areas major cities safety precautions",
        ),
        trigger_keywords=(
            "우범지역",
            "위험한 곳",
            "위험한곳",
            "위험지역",
            "조심해야 할 곳",
            "조심할 곳",
            "치안",
            "범죄",
            "밤에 위험",
            "unsafe area",
            "dangerous area",
            "crime-prone",
            "crime area",
        ),
        boost_keywords=(
            "주요 도시별 우범지역",
            "우범지역",
            "crime-prone",
            "unsafe area",
            "dangerous area",
            "safety_contacts",
            "안전정보",
            "whic",
            "워킹홀리데이 인포센터",
            "kings cross",
            "redfern",
            "fortitude valley",
            "sunnybank hills",
            "northbridge",
            "woodville",
            "parramatta",
            "blacktown",
            "central역",
            "시드니",
            "브리즈번",
            "멜번",
            "퍼스",
            "애들레이드",
            "호바트",
        ),
        downrank_keywords=("natural disaster", "산불", "홍수", "폭우"),
    ),
    "emergency_contact": SearchStrategy(
        intent="emergency_contact",
        category="life",
        priority_queries=(
            "Australia emergency number 000 Korean embassy consulate emergency contact consular call center",
            "호주 긴급전화 000 영사콜센터 주호주 대한민국 대사관 총영사관 사건사고 연락처",
        ),
        trigger_keywords=(
            "응급",
            "긴급",
            "사고",
            "영사",
            "공관",
            "대사관",
            "총영사관",
            "전화",
            "연락",
            "emergency",
            "consular",
        ),
        boost_keywords=("000", "긴급", "영사", "공관", "대사관", "총영사관", "consular", "emergency"),
    ),
    "visa_cost_duration": SearchStrategy(
        intent="visa_cost_duration",
        category="visa",
        priority_queries=(
            "Australia working holiday visa 417 application cost processing time duration WHIC Home Affairs",
            "호주 워홀비자 비용 소요시간 체류기간 문의처 WHIC",
        ),
        trigger_keywords=("비용", "가격", "얼마", "처리기간", "소요시간", "체류기간", "cost", "duration"),
        boost_keywords=("비용", "소요시간", "처리기간", "duration", "cost", "whic", "home affairs"),
    ),
    "unpaid_wage": SearchStrategy(
        intent="unpaid_wage",
        category="labor_law",
        priority_queries=(
            "Fair Work Ombudsman unpaid wages underpayment workplace problems recover wages",
            "호주 임금 체불 급여 미지급 Fair Work Ombudsman workplace problem",
        ),
        trigger_keywords=("임금 체불", "돈을 못 받", "급여 미지급", "underpayment", "unpaid wage", "wage theft"),
        boost_keywords=("fair work", "unpaid", "underpayment", "workplace problem", "recover wages", "임금", "미지급"),
    ),
    "tax_tfn": SearchStrategy(
        intent="tax_tfn",
        category="tax",
        priority_queries=(
            "Australian Taxation Office tax file number TFN working holiday maker application",
            "ATO TFN tax file number working holiday maker",
        ),
        trigger_keywords=("tfn", "세금파일번호", "tax file number"),
        boost_keywords=("ato", "tax file number", "tfn", "working holiday maker"),
    ),
    "superannuation": SearchStrategy(
        intent="superannuation",
        category="tax",
        priority_queries=(
            "Australian Taxation Office superannuation DASP departing Australia super payment working holiday maker",
            "ATO superannuation DASP refund working holiday maker",
        ),
        trigger_keywords=("super", "슈퍼", "연금", "dasp", "superannuation"),
        boost_keywords=("ato", "superannuation", "dasp", "departing australia", "super"),
    ),
    "housing_scam": SearchStrategy(
        intent="housing_scam",
        category="life",
        priority_queries=(
            "Australia working holiday share house rental scam bond contract precautions",
            "호주 워킹홀리데이 숙소 쉐어하우스 온라인 사기 보증금 계약 주의사항",
        ),
        trigger_keywords=("숙소", "쉐어", "집", "렌트", "보증금", "사기", "계약", "housing", "share house", "rental scam"),
        boost_keywords=("숙소", "share", "rental", "scam", "bond", "contract", "온라인 사기", "계약"),
    ),
}


def _normalize(text: str) -> str:
    return text.lower().replace(" ", "")


def payload_search_text(payload: dict) -> str:
    return " ".join(
        str(payload.get(key, "") or "")
        for key in [
            "title",
            "section",
            "source",
            "source_name",
            "source_provider",
            "document_type",
            "date",
            "last_updated",
            "text",
        ]
    ).lower()


def select_search_strategy(
    *,
    intent: str | None,
    user_message: str,
    search_query: str,
) -> SearchStrategy | None:
    if intent in SEARCH_STRATEGIES:
        return SEARCH_STRATEGIES[intent]

    normalized = _normalize(f"{user_message} {search_query}")
    for strategy in SEARCH_STRATEGIES.values():
        if any(_normalize(keyword) in normalized for keyword in strategy.trigger_keywords):
            return strategy
    return None


def rerank_chunks_for_strategy(chunks: list[dict], strategy: SearchStrategy) -> list[dict]:
    reranked: list[dict] = []

    for chunk in chunks:
        payload = chunk.get("payload", {})
        text = payload_search_text(payload)
        score = float(chunk.get("score", 0) or 0)

        bonus = 0.0
        for keyword in strategy.boost_keywords:
            keyword_norm = keyword.lower()
            if keyword_norm and keyword_norm in text:
                bonus += 0.08

        for keyword in strategy.downrank_keywords:
            keyword_norm = keyword.lower()
            if keyword_norm and keyword_norm in text:
                bonus -= 0.08

        reranked.append({**chunk, "score": score + bonus})

    return sorted(reranked, key=lambda item: item.get("score", 0), reverse=True)
