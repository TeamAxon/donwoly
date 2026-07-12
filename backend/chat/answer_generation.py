from typing import Literal

from pydantic import BaseModel, Field

from chat import openai_client


VERIFICATION_SYSTEM_PROMPT = """
당신은 호주 워킹홀리데이 전문 상담 챗봇입니다.
사용자 정보: 나이 {age}세, 거주/예정 지역 {region}, 업종 {industry}
카테고리: {category}

아래 참고 문서를 근거로만 답변하세요.
참고 문서:
{retrieved_chunks}

이전 대화 맥락:
{conversation_history}

사용자 질문: {user_query}

주의:
- 이전 대화는 현재 질문의 생략된 주어, 대상, 맥락을 이해하는 데만 사용하세요.
- 사실 판단과 구체적인 안내는 반드시 참고 문서 근거 안에서만 답변하세요.
- 참고 문서는 영어로 되어 있을 수 있습니다. 문서 내용을 이해한 뒤 반드시 한국어로 답변하세요.
- 참고 문서의 영어 원문을 그대로 번역해서 붙여넣지 말고, 자연스러운 한국어 설명으로 재구성하세요.
- 참고 문서에 명확한 근거가 없으면 grounded=false, confidence=low로 판단하세요.
- 문서 내용을 추측하거나 지어내지 마세요.
- 비자, 세금, 노동법에 대해 최종 법적 판단처럼 단정하지 마세요.
- 답변에 "외교부 공공데이터 및 공식 출처 기준"이라는 표현을 포함하세요.
- 답변은 한국어로 쉽고 구체적으로 작성하세요.
""".strip()

FALLBACK_MESSAGE = (
    "제공된 공식 자료만으로는 확인하기 어렵습니다. "
    "Donwoly는 외교부 공공데이터 및 공식 출처 기준으로만 답변하므로, "
    "질문을 조금 더 구체적으로 입력하거나 관련 공식기관 안내를 직접 확인해주세요."
)


class GeneratedAnswer(BaseModel):
    answer: str = Field(min_length=1)
    grounded: bool
    confidence: Literal["high", "medium", "low"]


def _format_conversation_history(
    conversation_history: list[dict[str, str]] | None,
    *,
    limit: int = 8,
    max_chars_per_message: int = 700,
) -> str:
    if not conversation_history:
        return "이전 대화 없음"

    lines: list[str] = []
    for message in conversation_history[-limit:]:
        role = "사용자" if message.get("role") == "user" else "Donwoly"
        content = (message.get("content") or "").strip()
        if not content:
            continue
        if len(content) > max_chars_per_message:
            content = f"{content[:max_chars_per_message]}..."
        lines.append(f"{role}: {content}")
    return "\n".join(lines) or "이전 대화 없음"


async def generate_answer(
    user_message: str,
    retrieved_chunks: list[dict],
    user_profile: dict,
    category: str | None,
    conversation_history: list[dict[str, str]] | None = None,
) -> dict:
    """
    GPT-5 한 번 호출로 답변 + 자체 확신도(grounded/confidence)를 구조화된 JSON으로 받음.
    확신도가 낮으면 fallback 메시지로 교체 ("모르겠다"고 솔직하게 답변).

    반환: {"answer": str, "grounded": bool, "confidence": str}
    """
    if not retrieved_chunks:
        return {"answer": FALLBACK_MESSAGE, "grounded": False, "confidence": "low"}

    retrieved_text = "\n\n".join(
        chunk.get("payload", {}).get("text", "") for chunk in retrieved_chunks
    )
    prompt = VERIFICATION_SYSTEM_PROMPT.format(
        age=user_profile["age"],
        region=user_profile["region"],
        industry=user_profile["industry"],
        category=category or "미분류",
        retrieved_chunks=retrieved_text,
        conversation_history=_format_conversation_history(conversation_history),
        user_query=user_message,
    )
    result = await openai_client.parse_structured(
        [{"role": "system", "content": prompt}], GeneratedAnswer
    )

    if not result.grounded or result.confidence == "low":
        return {"answer": FALLBACK_MESSAGE, "grounded": False, "confidence": "low"}
    return result.model_dump(mode="json")
