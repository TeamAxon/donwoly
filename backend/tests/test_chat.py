import json


def parse_sse(response):
    events = []
    for block in response.text.strip().split("\n\n"):
        lines = block.splitlines()
        event = next(line[6:].strip() for line in lines if line.startswith("event:"))
        data = json.loads(next(line[5:].strip() for line in lines if line.startswith("data:")))
        events.append((event, data))

    meta = next(data for event, data in events if event == "meta")
    chunks = [data["answerChunk"] for event, data in events if event == "chunk"]
    sources = next(data["sources"] for event, data in events if event == "sources")
    return {
        **meta,
        "answerChunk": "".join(chunks),
        "sources": sources,
        "events": events,
    }


def signup_user(client, email="chat@example.com"):
    response = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "name": "챗사용자",
            "password": "Password1!",
            "age": 27,
            "region": "PERTH",
            "industry": "FARM",
        },
    )
    assert response.status_code == 201
    return response.json()


def auth_headers(tokens):
    return {"Authorization": f"Bearer {tokens['accessToken']}"}


def test_query_requires_access_token(client):
    response = client.post("/api/chat/query", json={"message": "비자 조건 알려줘"})

    assert response.status_code == 401
    assert response.json() == {"error": "UNAUTHORIZED"}


def test_refresh_token_cannot_access_chat(client):
    tokens = signup_user(client)
    response = client.post(
        "/api/chat/query",
        headers={"Authorization": f"Bearer {tokens['refreshToken']}"},
        json={"message": "비자 조건 알려줘"},
    )

    assert response.status_code == 401
    assert response.json() == {"error": "UNAUTHORIZED"}


def test_new_query_returns_spec_fields_and_personalized_mock(client):
    tokens = signup_user(client)
    response = client.post(
        "/api/chat/query",
        headers=auth_headers(tokens),
        json={"message": "농장에서 일할 때 최저임금은?", "category": "labor"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = parse_sse(response)
    assert {"conversationId", "messageId", "answerChunk", "sources"} <= set(body)
    assert "맞춤 테스트 답변" in body["answerChunk"]
    assert "PERTH, FARM, 27세" in body["answerChunk"]
    assert body["sources"][0]["url"] == "https://www.fairwork.gov.au/"
    assert [event for event, _ in body["events"]] == [
        "meta",
        "chunk",
        "chunk",
        "sources",
        "done",
    ]


def test_follow_up_query_and_conversation_endpoints(client):
    tokens = signup_user(client)
    headers = auth_headers(tokens)
    first = parse_sse(client.post(
        "/api/chat/query",
        headers=headers,
        json={"message": "TFN이 필요해?", "category": "tax"},
    ))
    second = client.post(
        "/api/chat/query",
        headers=headers,
        json={
            "message": "신청은 어떻게 해?",
            "category": "tax",
            "conversationId": first["conversationId"],
        },
    )

    assert second.status_code == 200
    assert parse_sse(second)["conversationId"] == first["conversationId"]

    conversations = client.get("/api/chat/conversations", headers=headers)
    messages = client.get(
        f"/api/chat/conversations/{first['conversationId']}/messages", headers=headers
    )
    assert conversations.status_code == 200
    assert len(conversations.json()) == 1
    assert len(messages.json()) == 4
    assert [item["role"] for item in messages.json()] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]


def test_invalid_category_and_blank_message_return_validation_error(client):
    tokens = signup_user(client)
    headers = auth_headers(tokens)

    invalid_category = client.post(
        "/api/chat/query",
        headers=headers,
        json={"message": "질문", "category": "housing"},
    )
    blank_message = client.post(
        "/api/chat/query", headers=headers, json={"message": "   "}
    )

    assert invalid_category.status_code == 422
    assert invalid_category.json()["error"] == "VALIDATION_ERROR"
    assert blank_message.status_code == 422
    assert blank_message.json()["error"] == "VALIDATION_ERROR"


def test_conversation_is_private_to_owner(client):
    owner = signup_user(client, "owner@example.com")
    other = signup_user(client, "other@example.com")
    conversation = parse_sse(client.post(
        "/api/chat/query",
        headers=auth_headers(owner),
        json={"message": "내 대화"},
    ))

    response = client.get(
        f"/api/chat/conversations/{conversation['conversationId']}/messages",
        headers=auth_headers(other),
    )

    assert response.status_code == 404
    assert response.json() == {"error": "CONVERSATION_NOT_FOUND"}


def test_delete_conversation(client):
    tokens = signup_user(client)
    headers = auth_headers(tokens)
    conversation = parse_sse(client.post(
        "/api/chat/query", headers=headers, json={"message": "삭제할 대화"}
    ))
    url = f"/api/chat/conversations/{conversation['conversationId']}"

    deleted = client.delete(url, headers=headers)
    missing = client.get(f"{url}/messages", headers=headers)

    assert deleted.status_code == 204
    assert deleted.content == b""
    assert missing.status_code == 404


def test_openai_failure_streams_and_stores_fallback_message(client, monkeypatch):
    from chat import openai_client

    async def fail_parse(input_messages, response_model):
        raise openai_client.AIServiceError(
            "provider unavailable", reason="openai_insufficient_quota"
        )

    monkeypatch.setattr(openai_client, "parse_structured", fail_parse)
    tokens = signup_user(client)
    headers = auth_headers(tokens)
    response = client.post(
        "/api/chat/query",
        headers=headers,
        json={"message": "비자 질문"},
    )

    assert response.status_code == 200
    body = parse_sse(response)
    assert "OpenAI API 크레딧" in body["answerChunk"]
    messages = client.get(
        f"/api/chat/conversations/{body['conversationId']}/messages", headers=headers
    )
    assert [item["role"] for item in messages.json()] == ["user", "assistant"]
    assert "OpenAI API 크레딧" in messages.json()[1]["content"]


def test_qdrant_failure_streams_and_stores_fallback_message(client, monkeypatch):
    from rag import qdrant_search

    class BrokenQdrant:
        def query_points(self, **kwargs):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(qdrant_search, "_get_qdrant_client", lambda: BrokenQdrant())
    tokens = signup_user(client)
    headers = auth_headers(tokens)
    response = client.post(
        "/api/chat/query",
        headers=headers,
        json={"message": "생활 질문", "category": "life"},
    )

    assert response.status_code == 200
    body = parse_sse(response)
    assert "공식 자료 검색 서비스" in body["answerChunk"]
    messages = client.get(
        f"/api/chat/conversations/{body['conversationId']}/messages", headers=headers
    )
    assert [item["role"] for item in messages.json()] == ["user", "assistant"]
    assert "공식 자료 검색 서비스" in messages.json()[1]["content"]
