import os

os.environ["JWT_SECRET"] = "test-only-secret-that-is-long-enough-for-tests"

import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from chat.repository import conversation_repository
from chat import openai_client
from chat.answer_generation import GeneratedAnswer
from chat.query_understanding import QueryInterpretation
from main import app
from rag import qdrant_search


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def clear_conversations():
    conversation_repository.clear()


@pytest.fixture(autouse=True)
def mock_openai_structured_output(monkeypatch):
    async def fake_parse(input_messages, response_model):
        content = "\n".join(message["content"] for message in input_messages)
        if response_model is QueryInterpretation:
            if "TFN" in content or "세금" in content or "신청은 어떻게" in content:
                categories = ["tax"]
            elif "비자" in content:
                categories = ["visa"]
            elif "최저임금" in content or "노동" in content:
                categories = ["labor"]
            else:
                categories = ["life"]
            return QueryInterpretation(
                categories=categories, search_query="테스트용으로 재작성된 검색 쿼리"
            )
        if response_model is GeneratedAnswer:
            return GeneratedAnswer(
                answer="PERTH, FARM, 27세 프로필을 반영한 맞춤 테스트 답변",
                grounded=True,
                confidence="high",
            )
        raise AssertionError(f"Unexpected response model: {response_model}")

    monkeypatch.setattr(openai_client, "parse_structured", fake_parse)


@pytest.fixture(autouse=True)
def mock_embedding_and_qdrant_clients(monkeypatch):
    class FakeEmbeddings:
        def create(self, model, input):
            return SimpleNamespace(
                data=[SimpleNamespace(embedding=[0.01] * qdrant_search.EMBEDDING_SIZE)]
            )

    class FakeOpenAIClient:
        embeddings = FakeEmbeddings()

    class FakeQdrantClient:
        def query_points(
            self,
            collection_name,
            query,
            query_filter,
            limit,
            with_payload,
            with_vectors,
        ):
            category = "life"
            if query_filter is not None:
                category = query_filter.must[0].match.value
            urls = {
                "visa": "https://immi.homeaffairs.gov.au/",
                "departure": "https://www.australia.com/",
                "labor": "https://www.fairwork.gov.au/",
                "tax": "https://www.ato.gov.au/",
                "life": "https://www.australia.gov.au/",
            }
            point = SimpleNamespace(
                id=f"{category}_test_0",
                score=0.9,
                payload={
                    "category": category,
                    "title": f"{category} 테스트 문서",
                    "source": urls[category],
                    "text": f"{category} 테스트 근거",
                },
            )
            return SimpleNamespace(points=[point][:limit])

    monkeypatch.setattr(qdrant_search, "_get_openai_client", lambda: FakeOpenAIClient())
    monkeypatch.setattr(qdrant_search, "_get_qdrant_client", lambda: FakeQdrantClient())
    yield
    conversation_repository.clear()
