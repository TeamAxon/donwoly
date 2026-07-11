import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from models import ChatMessage, Conversation


StoredConversation = Conversation
StoredMessage = ChatMessage


class ConversationRepository:
    """Persistent chat history store backed by Postgres."""

    def create(
        self, db: Session, user_id: uuid.UUID, first_message: str
    ) -> StoredConversation:
        title = first_message.strip().replace("\n", " ")[:40] or "새 대화"
        conversation = Conversation(user_id=user_id, title=title)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation

    def get_for_user(
        self, db: Session, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> StoredConversation | None:
        statement = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        )
        return db.scalars(statement).first()

    def list_for_user(self, db: Session, user_id: uuid.UUID) -> list[StoredConversation]:
        statement = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        )
        return list(db.scalars(statement).all())

    def add_message(
        self,
        db: Session,
        conversation: StoredConversation,
        role: str,
        content: str,
        sources: list[dict] | None = None,
    ) -> StoredMessage:
        message = ChatMessage(
            conversation_id=conversation.id,
            role=role,
            content=content,
            sources=sources or [],
        )
        conversation.updated_at = datetime.now(UTC)
        db.add(message)
        db.add(conversation)
        db.commit()
        db.refresh(message)
        db.refresh(conversation)
        return message

    def delete_for_user(
        self, db: Session, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        conversation = self.get_for_user(db, conversation_id, user_id)
        if conversation is None:
            return False
        db.delete(conversation)
        db.commit()
        return True

    def clear(self) -> None:
        # Tests use a fresh DB per case. This method keeps old test hooks harmless.
        return None


conversation_repository = ConversationRepository()
