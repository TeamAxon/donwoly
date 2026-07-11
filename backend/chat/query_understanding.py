from pydantic import BaseModel, Field

from chat import openai_client
from chat.schemas import ChatCategory


QUERY_UNDERSTANDING_SYSTEM_PROMPT = """
당신은 호주 워킹홀리데이 상담 검색 쿼리 분석기입니다.
사용자 질문을 다음 고정 카테고리 중에서만 분류하세요:
visa, departure, labor_law, tax, life.
여러 주제에 걸치면 관련 카테고리를 모두 반환하고, 관련이 없으면 빈 배열을 반환하세요.
사용자의 나이, 지역, 업종을 반영해 Qdrant 검색에 적합한 한국어 검색 문장으로 재작성하세요.
질문에 없는 사실을 추가하거나 답변을 생성하지 마세요.
""".strip()


class QueryInterpretation(BaseModel):
    categories: list[ChatCategory] = Field(max_length=5)
    search_query: str = Field(min_length=1, max_length=1000)


async def interpret_query(user_message: str, user_profile: dict) -> dict:
    """
    1) 질문 카테고리 자동 분류 (visa/departure/labor_law/tax/life 중, 애매하면 복수 가능)
    2) Qdrant 검색에 쓸 쿼리 재작성 (구어체 → 검색 최적화 문장)
    """
    profile_context = (
        f"나이: {user_profile['age']}세\n"
        f"지역: {user_profile['region']}\n"
        f"업종: {user_profile['industry']}"
    )
    result = await openai_client.parse_structured(
        [
            {"role": "system", "content": QUERY_UNDERSTANDING_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"사용자 프로필:\n{profile_context}\n\n사용자 질문:\n{user_message}",
            },
        ],
        QueryInterpretation,
    )
    return result.model_dump(mode="json")
