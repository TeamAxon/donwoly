import os
from typing import TypeVar

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel


StructuredOutput = TypeVar("StructuredOutput", bound=BaseModel)


class AIServiceError(RuntimeError):
    pass


def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-5")


async def parse_structured(
    input_messages: list[dict[str, str]], response_model: type[StructuredOutput]
) -> StructuredOutput:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise AIServiceError("OPENAI_API_KEY environment variable is required")

    try:
        client = AsyncOpenAI(api_key=api_key)
        response = await client.responses.parse(
            model=get_openai_model(),
            input=input_messages,
            text_format=response_model,
        )
    except OpenAIError as exc:
        raise AIServiceError("OpenAI request failed") from exc

    if response.output_parsed is None:
        raise AIServiceError("OpenAI returned no structured output")
    return response.output_parsed
