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

사용자 질문: {user_query}

주의:
- 참고 문서에 명확한 근거가 없으면 grounded=false, confidence=low로 판단하세요.
- 문서 내용을 추측하거나 지어내지 마세요.
- 답변은 한국어로 쉽고 구체적으로 작성하세요.
""".strip()

FALLBACK_MESSAGE = (
    "죄송해요, 지금 갖고 있는 정보만으로는 확실하게 답변드리기 어려워요. "
    "호주 이민성 공식 사이트(https://immi.homeaffairs.gov.au)나 관련 기관에 "
    "직접 확인해보시는 걸 추천드려요. 질문을 조금 더 구체적으로 해주시면 다시 찾아볼게요!"
)


class GeneratedAnswer(BaseModel):
    answer: str = Field(min_length=1)
    grounded: bool
    confidence: Literal["high", "medium", "low"]


async def generate_answer(
    user_message: str,
    retrieved_chunks: list[dict],
    user_profile: dict,
    category: str | None,
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
        user_query=user_message,
    )
    result = await openai_client.parse_structured(
        [{"role": "system", "content": prompt}], GeneratedAnswer
    )

    if not result.grounded or result.confidence == "low":
        return {"answer": FALLBACK_MESSAGE, "grounded": False, "confidence": "low"}
    return result.model_dump(mode="json")
