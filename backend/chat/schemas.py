import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatCategory(str, Enum):
    VISA = "visa"
    DEPARTURE = "departure"
    LABOR_LAW = "labor_law"
    TAX = "tax"
    LIFE = "life"


class ChatQueryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str = Field(min_length=1, max_length=2000)
    category: ChatCategory | None = None
    conversation_id: uuid.UUID | None = Field(default=None, alias="conversationId")

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be blank")
        return value


class SourceResponse(BaseModel):
    title: str
    url: str | None = None
    category: ChatCategory | None = None
    score: float | None = None


class ChatQueryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    conversation_id: uuid.UUID = Field(serialization_alias="conversationId")
    message_id: uuid.UUID = Field(serialization_alias="messageId")
    answer_chunk: str = Field(serialization_alias="answerChunk")
    sources: list[SourceResponse] = Field(default_factory=list)


class ConversationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: uuid.UUID
    title: str
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class MessageResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: uuid.UUID
    role: str
    content: str
    sources: list[SourceResponse] = Field(default_factory=list)
    created_at: datetime = Field(serialization_alias="createdAt")
