import pytest

from chat import openai_client
from chat.answer_generation import FALLBACK_MESSAGE, GeneratedAnswer, generate_answer
from chat.query_understanding import QueryInterpretation, interpret_query
from rag import answer_service


PROFILE = {"age": 25, "region": "SYDNEY", "industry": "HOSPITALITY"}


@pytest.mark.anyio
async def test_interpret_query_injects_profile_and_returns_structured_dict(monkeypatch):
    captured = {}

    async def capture(input_messages, response_model):
        captured["messages"] = input_messages
        assert response_model is QueryInterpretation
        return QueryInterpretation(
            category="tax",
            intent="tax_tfn",
            search_query_en="Australian income tax deductions from hospitality wages",
        )

    monkeypatch.setattr(openai_client, "parse_structured", capture)
    result = await interpret_query("급여에서 세금이 얼마나 빠져?", PROFILE)

    prompt = captured["messages"][1]["content"]
    assert "25세" in prompt
    assert "SYDNEY" in prompt
    assert "HOSPITALITY" in prompt
    assert result == {
        "category": "tax",
        "intent": "tax_tfn",
        "search_query_en": "Australian income tax deductions from hospitality wages",
    }
    system_prompt = captured["messages"][0]["content"]
    assert "영어 검색 쿼리" in system_prompt
    assert "법률·행정·공식기관" in system_prompt


@pytest.mark.anyio
async def test_generate_answer_falls_back_without_chunks(monkeypatch):
    async def must_not_call(*args, **kwargs):
        raise AssertionError("OpenAI should not be called without retrieved chunks")

    monkeypatch.setattr(openai_client, "parse_structured", must_not_call)
    result = await generate_answer("질문", [], PROFILE, None)

    assert result == {
        "answer": FALLBACK_MESSAGE,
        "grounded": False,
        "confidence": "low",
    }


@pytest.mark.anyio
async def test_generate_answer_replaces_low_confidence_result(monkeypatch):
    captured = {}

    async def low_confidence(input_messages, response_model):
        captured["prompt"] = input_messages[0]["content"]
        assert response_model is GeneratedAnswer
        return GeneratedAnswer(answer="근거 없는 답", grounded=False, confidence="low")

    monkeypatch.setattr(openai_client, "parse_structured", low_confidence)
    result = await generate_answer(
        "질문", [{"payload": {"text": "관련 문서"}}], PROFILE, "life"
    )

    assert result["answer"] == FALLBACK_MESSAGE
    assert result["grounded"] is False
    assert "반드시 한국어로 답변" in captured["prompt"]
    assert "자연스러운 한국어 설명으로 재구성" in captured["prompt"]


@pytest.mark.anyio
async def test_build_rag_answer_embeds_english_query_and_maps_sources(monkeypatch):
    searched_queries = []

    async def fake_interpret(user_message, user_profile):
        return {
            "category": "labor",
            "search_query_en": "Australian employee pay slip requirements",
        }

    def fake_search(query, category=None, top_k=5):
        searched_queries.append((query, category, top_k))
        return [
            {
                "id": category,
                "score": 0.9,
                "payload": {
                    "title": f"{category} 문서",
                    "source": f"https://example.com/{category}",
                    "text": "근거",
                },
            }
        ]

    async def fake_generate(
        user_message, chunks, user_profile, category, conversation_history=None
    ):
        assert category == "labor"
        assert conversation_history is None
        return {"answer": "근거 답변", "grounded": True, "confidence": "high"}

    monkeypatch.setattr(answer_service, "interpret_query", fake_interpret)
    monkeypatch.setattr(answer_service, "search_chunks", fake_search)
    monkeypatch.setattr(answer_service, "generate_answer", fake_generate)
    result = await answer_service.build_rag_answer("질문", PROFILE, None)

    assert searched_queries == [
        ("Australian employee pay slip requirements", "labor", 10),
    ]
    assert result["answer"] == "근거 답변"
    assert [source["score"] for source in result["sources"]] == [0.9]


@pytest.mark.anyio
async def test_build_rag_answer_uses_conversation_history_for_follow_up(monkeypatch):
    captured = {}

    async def fake_interpret(user_message, user_profile):
        captured["interpreted_message"] = user_message
        return {
            "category": "visa",
            "search_query_en": "Working Holiday visa character requirement Australia",
        }

    def fake_search(query, category=None, top_k=5):
        return [
            {
                "id": "visa_character",
                "score": 0.9,
                "payload": {
                    "title": "Character requirement",
                    "source": "https://example.com/character",
                    "text": "근거",
                },
            }
        ]

    async def fake_generate(
        user_message, chunks, user_profile, category, conversation_history=None
    ):
        captured["generated_history"] = conversation_history
        return {"answer": "근거 답변", "grounded": True, "confidence": "high"}

    history = [
        {"role": "user", "content": "호주 워홀 비자 신원 요건이 뭐야?"},
        {"role": "assistant", "content": "신원 요건은 character requirement입니다."},
    ]

    monkeypatch.setattr(answer_service, "interpret_query", fake_interpret)
    monkeypatch.setattr(answer_service, "search_chunks", fake_search)
    monkeypatch.setattr(answer_service, "generate_answer", fake_generate)
    result = await answer_service.build_rag_answer(
        "그건 어떻게 확인해?", PROFILE, None, conversation_history=history
    )

    assert "[이전 대화]" in captured["interpreted_message"]
    assert "신원 요건" in captured["interpreted_message"]
    assert captured["generated_history"] == history
    assert result["answer"] == "근거 답변"


@pytest.mark.anyio
async def test_safety_area_intent_uses_life_strategy_and_reranks(monkeypatch):
    searched = []
    captured = {}

    async def fake_interpret(user_message, user_profile):
        return {
            "category": "life",
            "intent": "safety_area",
            "search_query_en": "Australia WHIC crime-prone areas",
        }

    def fake_search(query, category=None, top_k=5):
        searched.append((query, category, top_k))
        return [
            {
                "id": "natural_disaster",
                "score": 0.7,
                "payload": {
                    "title": "자연재해 안전정보",
                    "category": "life",
                    "source": "https://example.com/natural",
                    "text": "산불 홍수 폭우 natural disaster",
                },
            },
            {
                "id": "crime_area",
                "score": 0.65,
                "payload": {
                    "title": "호주 안전정보와 긴급 연락처 원문 상세",
                    "category": "life",
                    "source": "https://example.com/safety",
                    "text": "▣ 주요 도시별 우범지역 시드니 Kings Cross Redfern 브리즈번 Fortitude Valley",
                },
            },
        ]

    async def fake_generate(
        user_message, chunks, user_profile, category, conversation_history=None
    ):
        captured["category"] = category
        captured["first_title"] = chunks[0]["payload"]["title"]
        return {"answer": "근거 답변", "grounded": True, "confidence": "high"}

    monkeypatch.setattr(answer_service, "interpret_query", fake_interpret)
    monkeypatch.setattr(answer_service, "search_chunks", fake_search)
    monkeypatch.setattr(answer_service, "generate_answer", fake_generate)
    result = await answer_service.build_rag_answer(
        "내가 워홀가는 지역에 위험한 곳 있어?", PROFILE, None
    )

    assert result["answer"] == "근거 답변"
    assert captured == {
        "category": "life",
        "first_title": "호주 안전정보와 긴급 연락처 원문 상세",
    }
    assert {category for _, category, _ in searched} == {"life"}
    assert max(top_k for _, _, top_k in searched) == 30


@pytest.mark.anyio
async def test_explicit_category_overrides_interpreted_category(monkeypatch):
    async def fake_interpret(user_message, user_profile):
        return {"category": "life", "search_query_en": "hospital costs"}

    searched = {}

    def fake_search(query, category=None, top_k=5):
        searched.update(query=query, category=category)
        return []

    monkeypatch.setattr(answer_service, "interpret_query", fake_interpret)
    monkeypatch.setattr(answer_service, "search_chunks", fake_search)
    await answer_service.build_rag_answer("질문", PROFILE, "visa")

    assert searched == {"query": "emergency hospital costs", "category": "visa"}
