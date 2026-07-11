import os
from typing import TypeVar

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel


StructuredOutput = TypeVar("StructuredOutput", bound=BaseModel)


class AIServiceError(RuntimeError):
    def __init__(self, message: str, reason: str = "ai_service_unavailable") -> None:
        super().__init__(message)
        self.reason = reason


def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-5")


async def parse_structured(
    input_messages: list[dict[str, str]], response_model: type[StructuredOutput]
) -> StructuredOutput:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise AIServiceError(
            "OPENAI_API_KEY environment variable is required",
            reason="openai_api_key_missing",
        )

    try:
        client = AsyncOpenAI(api_key=api_key)
        response = await client.responses.parse(
            model=get_openai_model(),
            input=input_messages,
            text_format=response_model,
        )
    except OpenAIError as exc:
        reason = "ai_service_unavailable"
        if getattr(exc, "code", None) == "insufficient_quota" or getattr(
            exc, "status_code", None
        ) == 429:
            reason = "openai_insufficient_quota"
        raise AIServiceError("OpenAI request failed", reason=reason) from exc

    if response.output_parsed is None:
        raise AIServiceError("OpenAI returned no structured output")
    return response.output_parsed
