import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock


@dataclass
class StoredMessage:
    id: uuid.UUID
    role: str
    content: str
    sources: list[dict]
    created_at: datetime


@dataclass
class StoredConversation:
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[StoredMessage] = field(default_factory=list)


class InMemoryConversationRepository:
    """Milestone 5-3 store. TODO: replace with persistent DB storage."""

    def __init__(self) -> None:
        self._conversations: dict[uuid.UUID, StoredConversation] = {}
        self._lock = RLock()

    def create(self, user_id: uuid.UUID, first_message: str) -> StoredConversation:
        now = datetime.now(UTC)
        conversation = StoredConversation(
            id=uuid.uuid4(),
            user_id=user_id,
            title=first_message[:40],
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._conversations[conversation.id] = conversation
        return conversation

    def get_for_user(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> StoredConversation | None:
        with self._lock:
            conversation = self._conversations.get(conversation_id)
            if conversation is None or conversation.user_id != user_id:
                return None
            return conversation

    def list_for_user(self, user_id: uuid.UUID) -> list[StoredConversation]:
        with self._lock:
            items = [c for c in self._conversations.values() if c.user_id == user_id]
            return sorted(items, key=lambda item: item.updated_at, reverse=True)

    def add_message(
        self,
        conversation: StoredConversation,
        role: str,
        content: str,
        sources: list[dict] | None = None,
    ) -> StoredMessage:
        message = StoredMessage(
            id=uuid.uuid4(),
            role=role,
            content=content,
            sources=sources or [],
            created_at=datetime.now(UTC),
        )
        with self._lock:
            conversation.messages.append(message)
            conversation.updated_at = message.created_at
        return message

    def delete_for_user(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        with self._lock:
            conversation = self._conversations.get(conversation_id)
            if conversation is None or conversation.user_id != user_id:
                return False
            del self._conversations[conversation_id]
            return True

    def clear(self) -> None:
        with self._lock:
            self._conversations.clear()


conversation_repository = InMemoryConversationRepository()
