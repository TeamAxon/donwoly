from pydantic import BaseModel, Field

from chat import openai_client
from chat.schemas import ChatCategory


QUERY_UNDERSTANDING_SYSTEM_PROMPT = """
당신은 호주 워킹홀리데이 공식 문서 검색을 위한 쿼리 분석기입니다.
한 번의 응답에서 다음 세 작업을 모두 수행하세요.

1. 사용자 질문의 주된 카테고리를 visa, departure, labor_law, tax, life 중 하나로
   분류하세요. 어느 카테고리에도 해당하지 않으면 null을 반환하세요.
   - visa: 워킹홀리데이 비자, 세컨·서드 비자, 자격과 체류 조건
   - departure: 출국 전 준비, 입국, 준비물과 초기 행정
   - labor_law: 고용, 임금, 급여명세서, 근로조건과 직장 권리
   - tax: TFN, 소득세, 세금 신고와 superannuation
   - life: 의료·응급실·보험·주거·교통·치안·우범지역·긴급연락처 등 호주 현지 생활
   호주 워홀 생활과 관련된 실용 질문은 가능한 한 가장 가까운 카테고리를
   선택하고, null은 다섯 범주와 정말 무관한 질문에만 사용하세요.
2. 사용자 질문의 intent를 아래 값 중 하나로 분류하세요.
   해당하지 않으면 null을 반환하세요.
   - minimum_wage: 최저임금, 시급, pay rate
   - safety_area: 우범지역, 위험한 지역, 치안, 범죄 위험
   - emergency_contact: 응급전화, 영사콜센터, 공관 연락처, 사고 발생 시 연락
   - visa_cost_duration: 비자 비용, 처리기간, 체류기간
   - visa_requirement: 비자 자격, 조건, 필요서류, 신청 절차
   - unpaid_wage: 임금 체불, 급여 미지급, underpayment
   - tax_tfn: TFN, 세금파일번호
   - superannuation: super, 연금, DASP 환급
   - housing_scam: 숙소, 쉐어하우스, 계약, 보증금, 사기
3. 한국어 사용자 질문을 자연스러운 영어 검색 쿼리로 번역하고 재작성하세요.
   단순 직역이 아니라 호주 법률·행정·공식기관 문서에서 실제로 사용할 법한
   정확한 영어 용어를 사용하세요. 사용자의 지역과 업종은 관련 있을 때만 반영하세요.

예시:
- "세컨비자 조건이 뭐야?" → "second working holiday visa eligibility requirements"
- "월급 명세서 언제까지 줘야 돼?" → "Australian employer deadline for providing employee pay slips"
- "응급실 가면 돈 얼마나 나와?" → "cost of visiting an emergency department in Australia"
- "내가 가는 지역에 위험한 곳 있어?" → "Australia WHIC major city crime-prone areas unsafe areas safety precautions"
- "시드니 우범지역 알려줘" → "Sydney crime-prone areas Kings Cross Central Redfern safety precautions WHIC"
- "TFN은 왜 필요해?" → "Australian Taxation Office tax file number working holiday maker"
- "집 구할 때 사기 조심할 점 있어?" → "Australia working holiday share house rental scam bond contract precautions"

search_query_en에는 검색에 사용할 영어 문장만 넣으세요.
질문에 없는 사실을 추가하거나 질문에 대한 답변을 생성하지 마세요.
""".strip()


class QueryInterpretation(BaseModel):
    category: ChatCategory | None = None
    intent: str | None = None
    search_query_en: str = Field(min_length=1, max_length=1000)


async def interpret_query(user_message: str, user_profile: dict) -> dict:
    """
    1) 질문 카테고리 자동 분류 (visa/departure/labor_law/tax/life 중 하나 또는 None)
    2) Qdrant 검색에 쓸 자연스러운 영어 검색 쿼리로 번역 및 재작성
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
