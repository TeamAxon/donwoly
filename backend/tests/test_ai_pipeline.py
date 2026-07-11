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
            categories=["labor", "tax"], search_query="NSW hospitality 급여 세금"
        )

    monkeypatch.setattr(openai_client, "parse_structured", capture)
    result = await interpret_query("급여에서 세금이 얼마나 빠져?", PROFILE)

    prompt = captured["messages"][1]["content"]
    assert "25세" in prompt
    assert "SYDNEY" in prompt
    assert "HOSPITALITY" in prompt
    assert result == {
        "categories": ["labor", "tax"],
        "search_query": "NSW hospitality 급여 세금",
    }


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
    async def low_confidence(input_messages, response_model):
        assert response_model is GeneratedAnswer
        return GeneratedAnswer(answer="근거 없는 답", grounded=False, confidence="low")

    monkeypatch.setattr(openai_client, "parse_structured", low_confidence)
    result = await generate_answer(
        "질문", [{"payload": {"text": "관련 문서"}}], PROFILE, "life"
    )

    assert result["answer"] == FALLBACK_MESSAGE
    assert result["grounded"] is False


@pytest.mark.anyio
async def test_build_rag_answer_searches_multiple_categories_and_maps_sources(monkeypatch):
    searched_categories = []

    async def fake_interpret(user_message, user_profile):
        return {"categories": ["labor", "tax"], "search_query": "재작성 검색어"}

    def fake_search(query, category=None, top_k=5):
        searched_categories.append((query, category, top_k))
        return [
            {
                "id": category,
                "score": 0.9 if category == "labor" else 0.8,
                "payload": {
                    "title": f"{category} 문서",
                    "source": f"https://example.com/{category}",
                    "text": "근거",
                },
            }
        ]

    async def fake_generate(user_message, chunks, user_profile, category):
        assert category == "labor,tax"
        return {"answer": "근거 답변", "grounded": True, "confidence": "high"}

    monkeypatch.setattr(answer_service, "interpret_query", fake_interpret)
    monkeypatch.setattr(answer_service, "search_chunks", fake_search)
    monkeypatch.setattr(answer_service, "generate_answer", fake_generate)
    result = await answer_service.build_rag_answer("질문", PROFILE, None)

    assert searched_categories == [
        ("재작성 검색어", "labor", 5),
        ("재작성 검색어", "tax", 5),
    ]
    assert result["answer"] == "근거 답변"
    assert [source["score"] for source in result["sources"]] == [0.9, 0.8]
