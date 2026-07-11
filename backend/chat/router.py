import uuid
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from chat.openai_client import AIServiceError
from chat.repository import StoredConversation, StoredMessage, conversation_repository
from chat.schemas import (
    ChatQueryRequest,
    ConversationResponse,
    MessageResponse,
)
from database import get_db
from models import User
from rag.answer_service import build_rag_answer
from rag.qdrant_search import QdrantSearchError


router = APIRouter(prefix="/api/chat", tags=["chat"])
CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]


SERVICE_FALLBACK_MESSAGES = {
    "openai_insufficient_quota": (
        "현재 OpenAI API 크레딧 또는 사용량 한도 문제로 답변을 생성하지 못했습니다. "
        "질문은 최근대화에 저장해두었으니, API 사용 가능 상태가 되면 다시 시도해주세요."
    ),
    "openai_api_key_missing": (
        "현재 OpenAI API 키가 설정되어 있지 않아 답변을 생성하지 못했습니다. "
        "질문은 최근대화에 저장해두었습니다."
    ),
    "ai_service_unavailable": (
        "현재 AI 응답 생성 서비스에 연결하지 못했습니다. "
        "질문은 최근대화에 저장해두었으니 잠시 후 다시 시도해주세요."
    ),
    "search_service_unavailable": (
        "현재 공식 자료 검색 서비스에 연결하지 못했습니다. "
        "질문은 최근대화에 저장해두었으니 잠시 후 다시 시도해주세요."
    ),
}


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


def _get_conversation(
    db: Session, conversation_id: uuid.UUID, user: User
) -> StoredConversation:
    conversation = conversation_repository.get_for_user(db, conversation_id, user.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail={"error": "CONVERSATION_NOT_FOUND"})
    return conversation


@router.post("/query")
async def query_chat(
    payload: ChatQueryRequest, user: CurrentUser, db: DbSession
) -> StreamingResponse:
    if payload.conversation_id is None:
        conversation = conversation_repository.create(db, user.id, payload.message)
    else:
        conversation = _get_conversation(db, payload.conversation_id, user)

    conversation_repository.add_message(db, conversation, "user", payload.message)
    user_profile = {"age": user.age, "region": user.region, "industry": user.industry}
    try:
        result = await build_rag_answer(
            payload.message,
            user_profile,
            payload.category.value if payload.category is not None else None,
        )
    except AIServiceError as exc:
        result = {
            "answer": SERVICE_FALLBACK_MESSAGES.get(
                exc.reason, SERVICE_FALLBACK_MESSAGES["ai_service_unavailable"]
            ),
            "sources": [],
            "error": exc.reason,
        }
    except QdrantSearchError:
        result = {
            "answer": SERVICE_FALLBACK_MESSAGES["search_service_unavailable"],
            "sources": [],
            "error": "search_service_unavailable",
        }

    answer = result["answer"]
    sources = [
        {
            "title": item["title"],
            "url": item.get("source"),
            "category": item.get("category"),
            "score": item.get("score"),
        }
        for item in result["sources"]
    ]
    assistant_message = conversation_repository.add_message(
        db, conversation, "assistant", answer, sources
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
def list_conversations(user: CurrentUser, db: DbSession) -> list[ConversationResponse]:
    return [
        _conversation_response(item)
        for item in conversation_repository.list_for_user(db, user.id)
    ]


@router.get(
    "/conversations/{conversation_id}/messages", response_model=list[MessageResponse]
)
def list_messages(
    conversation_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[MessageResponse]:
    conversation = _get_conversation(db, conversation_id, user)
    return [_message_response(item) for item in conversation.messages]


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> Response:
    deleted = conversation_repository.delete_for_user(db, conversation_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"error": "CONVERSATION_NOT_FOUND"})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
