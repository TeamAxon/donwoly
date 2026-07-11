import uuid
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse

from auth.dependencies import get_current_user
from chat.openai_client import AIServiceError
from chat.repository import StoredConversation, StoredMessage, conversation_repository
from chat.schemas import (
    ChatQueryRequest,
    ConversationResponse,
    MessageResponse,
)
from models import User
from rag.answer_service import build_rag_answer
from rag.qdrant_search import QdrantSearchError


router = APIRouter(prefix="/api/chat", tags=["chat"])
CurrentUser = Annotated[User, Depends(get_current_user)]


def _conversation_response(item: StoredConversation) -> ConversationResponse:
    return ConversationResponse(
        id=item.id,
        title=item.title,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _message_response(item: StoredMessage) -> MessageResponse:
    return MessageResponse(
        id=item.id,
        role=item.role,
        content=item.content,
        sources=item.sources,
        created_at=item.created_at,
    )


def _get_conversation(conversation_id: uuid.UUID, user: User) -> StoredConversation:
    conversation = conversation_repository.get_for_user(conversation_id, user.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail={"error": "CONVERSATION_NOT_FOUND"})
    return conversation


@router.post("/query")
async def query_chat(payload: ChatQueryRequest, user: CurrentUser) -> StreamingResponse:
    if payload.conversation_id is None:
        conversation = conversation_repository.create(user.id, payload.message)
    else:
        conversation = _get_conversation(payload.conversation_id, user)

    conversation_repository.add_message(conversation, "user", payload.message)
    user_profile = {"age": user.age, "region": user.region, "industry": user.industry}
    try:
        result = await build_rag_answer(
            payload.message,
            user_profile,
            payload.category.value if payload.category is not None else None,
        )
    except AIServiceError:
        raise HTTPException(
            status_code=502, detail={"error": "AI_SERVICE_UNAVAILABLE"}
        ) from None
    except QdrantSearchError:
        raise HTTPException(
            status_code=503, detail={"error": "SEARCH_SERVICE_UNAVAILABLE"}
        ) from None

    answer = result["answer"]
    sources = [
        {"title": item["title"], "url": item.get("source")}
        for item in result["sources"]
    ]
    assistant_message = conversation_repository.add_message(
        conversation, "assistant", answer, sources
    )
    async def event_stream() -> AsyncIterator[str]:
        yield _sse_event(
            "meta",
            {
                "conversationId": str(conversation.id),
                "messageId": str(assistant_message.id),
            },
        )
        for start in range(0, len(answer), 24):
            yield _sse_event("chunk", {"answerChunk": answer[start : start + 24]})
        yield _sse_event("sources", {"sources": sources})
        yield _sse_event("done", {})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_event(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"


@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(user: CurrentUser) -> list[ConversationResponse]:
    return [
        _conversation_response(item)
        for item in conversation_repository.list_for_user(user.id)
    ]


@router.get(
    "/conversations/{conversation_id}/messages", response_model=list[MessageResponse]
)
def list_messages(
    conversation_id: uuid.UUID, user: CurrentUser
) -> list[MessageResponse]:
    conversation = _get_conversation(conversation_id, user)
    return [_message_response(item) for item in conversation.messages]


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: uuid.UUID, user: CurrentUser) -> Response:
    deleted = conversation_repository.delete_for_user(conversation_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"error": "CONVERSATION_NOT_FOUND"})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
