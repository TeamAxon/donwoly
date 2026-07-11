from types import SimpleNamespace

import pytest

from chat.openai_client import AIServiceError
from rag import qdrant_search


def test_embed_query_uses_confirmed_model_and_returns_1536_vector(monkeypatch):
    captured = {}

    class Embeddings:
        def create(self, model, input):
            captured.update(model=model, input=input)
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.2] * 1536)])

    client = SimpleNamespace(embeddings=Embeddings())
    monkeypatch.setattr(qdrant_search, "_get_openai_client", lambda: client)

    vector = qdrant_search.embed_query("호주 최저임금")

    assert captured == {
        "model": "text-embedding-3-small",
        "input": "호주 최저임금",
    }
    assert len(vector) == 1536


def test_search_chunks_applies_category_filter_and_maps_payload(monkeypatch):
    captured = {}

    class Qdrant:
        def query_points(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                points=[
                    SimpleNamespace(
                        id="labor_0",
                        score=0.82,
                        payload={"category": "labor", "title": "최저임금", "text": "근거"},
                    )
                ]
            )

    monkeypatch.setattr(qdrant_search, "embed_query", lambda text: [0.1] * 1536)
    monkeypatch.setattr(qdrant_search, "_get_qdrant_client", lambda: Qdrant())
    result = qdrant_search.search_chunks("최저임금", category="labor", top_k=3)

    assert captured["collection_name"] == "first_month_guide"
    assert captured["limit"] == 3
    assert captured["with_payload"] is True
    assert captured["with_vectors"] is False
    assert captured["query_filter"].must[0].key == "category"
    assert captured["query_filter"].must[0].match.value == "labor"
    assert result == [
        {
            "id": "labor_0",
            "score": 0.82,
            "payload": {"category": "labor", "title": "최저임금", "text": "근거"},
        }
    ]


def test_search_chunks_without_category_has_no_filter(monkeypatch):
    captured = {}

    class Qdrant:
        def query_points(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(points=[])

    monkeypatch.setattr(qdrant_search, "embed_query", lambda text: [0.1] * 1536)
    monkeypatch.setattr(qdrant_search, "_get_qdrant_client", lambda: Qdrant())

    assert qdrant_search.search_chunks("일반 질문") == []
    assert captured["query_filter"] is None


def test_embed_query_rejects_unexpected_vector_size(monkeypatch):
    embeddings = SimpleNamespace(
        create=lambda **kwargs: SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1] * 10)]
        )
    )
    monkeypatch.setattr(
        qdrant_search,
        "_get_openai_client",
        lambda: SimpleNamespace(embeddings=embeddings),
    )

    with pytest.raises(AIServiceError, match="Unexpected embedding size"):
        qdrant_search.embed_query("질문")


def test_search_chunks_wraps_qdrant_failure(monkeypatch):
    class BrokenQdrant:
        def query_points(self, **kwargs):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(qdrant_search, "embed_query", lambda text: [0.1] * 1536)
    monkeypatch.setattr(
        qdrant_search, "_get_qdrant_client", lambda: BrokenQdrant()
    )

    with pytest.raises(qdrant_search.QdrantSearchError):
        qdrant_search.search_chunks("질문")


def test_search_chunks_validates_category_and_top_k():
    with pytest.raises(ValueError, match="unsupported category"):
        qdrant_search.search_chunks("질문", category="housing")
    with pytest.raises(ValueError, match="top_k"):
        qdrant_search.search_chunks("질문", top_k=0)
