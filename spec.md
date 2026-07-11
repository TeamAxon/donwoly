# 호주 워홀 준비/생활 지원 앱 — 개발 스펙 (spec.md)

> 담당 범위: 회원가입, 챗봇 서비스 백엔드(질문 해석 + 검색 + 답변 생성), 프론트엔드
> Qdrant에는 팀원이 임베딩 인제스천(청킹→임베딩→적재)까지만 완료 → 검색 쿼리 실행 로직과 답변 생성은 본 문서 범위에서 직접 구현
> 코딩 도구: Codex 사용 예정. 이 문서는 Codex에게 그대로 컨텍스트로 던져도 되는 수준으로 작성.

> **스펙 유지보수 원칙**: 기존 제품 범위, 외부 API 계약, DB 스키마, 보안 정책을 변경하지 않는 구현 세부사항(오류 문구, 내부 모듈 구성, 임시 개발 방침 등)은 Codex가 별도 승인 요청 없이 `spec.md`에 즉시 반영하고 완료 보고에 포함한다. 범위·계약·스키마·보안 정책의 중대한 변경은 기존처럼 사용자 확인 후 반영한다.

---

## 0. 프로젝트 한 줄 요약

호주 워킹홀리데이를 준비 중이거나 이미 체류 중인 사용자에게, 회원가입 시 입력한 프로필(지역/업종/나이 등)을 기반으로 **비자 · 출국준비 · 노동법 · 세금 · 생활** 5개 카테고리에 대해 RAG 기반 챗봇이 개인화된 답변을 제공하는 서비스.

---

## 1. 기술 스택 (가정 — 팀 내 확정 스택으로 교체 가능)

| 영역 | 스택 |
|---|---|
| 프론트엔드 | React + Vite + TypeScript + Tailwind CSS |
| 라우팅 | React Router |
| 상태관리 | Zustand 또는 React Query (서버 상태) |
| 백엔드 | FastAPI (Python 3.11+) |
| 인증 | JWT (access + refresh token), 비밀번호는 bcrypt 해싱 |
| 유저 DB | PostgreSQL |
| 벡터 DB | Qdrant (팀원 구현 완료, 컬렉션 `first_month_guide`. 본 서버에서는 내부 파이썬 함수 호출로만 사용 — 섹션 3.5 참고) |
| LLM | GPT-5 — 사용자 질문 해석(query understanding) + 최종 답변 생성 |
| 배포 | 미정 (Netlify/Vercel(정적) + Railway/Fly.io 가정) |

Codex 작업 시 이 표를 실제 확정 스택으로 먼저 바꿔서 진행할 것.

### 1.1 로컬 개발 환경 (docker-compose, 팀원 구성 확인 완료 — 프론트/백엔드/Qdrant 전부 포함)

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant-db
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
    env_file:
      - .env

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      - VITE_API_URL=http://localhost:8000
    depends_on:
      - backend

volumes:
  qdrant_data:
```

- **`backend`** (`./backend`): 채은이 만드는 FastAPI 백엔드. 8000번 포트, `.env`로 환경변수 주입. `.env`에 `QDRANT_URL=http://qdrant:6333` 필요 (컨테이너 내부 통신이므로 서비스 이름 사용).
- **`frontend`** (`./frontend`): React+Vite 프론트, 5173번 포트. `VITE_API_URL=http://localhost:8000`은 **브라우저(사용자 PC)에서 직접 백엔드를 호출**하는 값이라 `localhost`가 맞음 (컨테이너 간 통신이 아니라 브라우저 → 호스트 노출 포트 접근이기 때문). `node_modules`는 볼륨 마운트에서 제외시켜 컨테이너 자체 설치본을 씀 (로컬 OS와 바이너리 충돌 방지).
- **`qdrant`**: 6333(HTTP API), 6334(gRPC) 노출. 데이터는 `qdrant_data` named volume에 영구 저장.
- 참고: `backend`에 `depends_on: qdrant`가 빠져있음 — Qdrant가 늦게 뜨면 백엔드 시작 시 연결 실패할 수 있으니 추가 권장.

---

## 2. 회원가입 (Sign Up) 스펙

### 2.1 입력 필드

| 필드명 | 타입 | 필수 | 검증 규칙 |
|---|---|---|---|
| `email` (아이디) | string | Y | 이메일 형식 검증, 중복 체크 API 필요. 아이디로 사용 |
| `name` (이름) | string | Y | 2~20자 |
| `password` | string | Y | 8자 이상, 영문+숫자+특수문자 최소 1개 |
| `age` | int | Y | 18~99 (워홀 비자 연령 제한 고려 시 18~30/35 안내 문구 추가 권장) |
| `region` | enum (단일 선택) | Y | 아래 2.2 목록 |
| `industry` | enum (단일 선택) | Y | 아래 2.3 목록 |

소셜 로그인(카카오/구글 등)은 **현재 범위 아님** — 이메일+비밀번호 방식만 우선 구현.

회원가입 폼은 **한 화면 롱폼이 아니라 스텝형(step-by-step)**으로 구성 (토스 스타일 — 한 번에 하나씩 입력받고 자동 다음 단계 전환).

추천 스텝 순서:
1. 이메일 + 비밀번호
2. 이름 + 나이
3. 지역 선택 (카드형 UI)
4. 업종 선택 (카드형 UI)
5. 완료 → 온보딩 → 챗봇 진입

### 2.2 지역(도시) 목록 — 워홀 최다 지역 TOP 5

카드/리스트 선택 UI에 아래 형태로 노출:

```
⭐ 시드니 (Sydney, NSW)
⭐ 멜버른 (Melbourne, VIC)
⭐ 브리즈번 (Brisbane, QLD)
⭐ 퍼스 (Perth, WA)
⭐ 골드코스트 (Gold Coast, QLD)
```

+ "기타 지역 직접 입력" 옵션 하나 추가 권장 (드롭다운 마지막 항목 `기타`).

```ts
// region enum 예시
type Region =
  | "SYDNEY"
  | "MELBOURNE"
  | "BRISBANE"
  | "PERTH"
  | "GOLD_COAST"
  | "OTHER";

const REGION_OPTIONS: { code: Region; label: string }[] = [
  { code: "SYDNEY", label: "⭐ 시드니 (Sydney, NSW)" },
  { code: "MELBOURNE", label: "⭐ 멜버른 (Melbourne, VIC)" },
  { code: "BRISBANE", label: "⭐ 브리즈번 (Brisbane, QLD)" },
  { code: "PERTH", label: "⭐ 퍼스 (Perth, WA)" },
  { code: "GOLD_COAST", label: "⭐ 골드코스트 (Gold Coast, QLD)" },
  { code: "OTHER", label: "기타 지역" },
];
```

### 2.3 업종 목록 (워홀러 실제 취업 분포 기준, 조정 가능)

```ts
type Industry =
  | "FARM"        // 농장/과수원 (세컨비자 목적 다수)
  | "HOSPITALITY" // 카페/레스토랑/바
  | "CONSTRUCTION"// 건설/노동
  | "CLEANING"    // 청소/하우스키핑
  | "FACTORY"     // 공장/육가공
  | "OFFICE"      // 사무직/인턴
  | "TOURISM"     // 관광/투어
  | "OTHER";

const INDUSTRY_OPTIONS: { code: Industry; label: string }[] = [
  { code: "FARM", label: "🌾 농장/과수원" },
  { code: "HOSPITALITY", label: "☕ 카페/레스토랑/바" },
  { code: "CONSTRUCTION", label: "🏗️ 건설/현장" },
  { code: "CLEANING", label: "🧹 청소/하우스키핑" },
  { code: "FACTORY", label: "🏭 공장/육가공" },
  { code: "OFFICE", label: "💼 사무직/인턴" },
  { code: "TOURISM", label: "🧳 관광/투어" },
  { code: "OTHER", label: "기타" },
];
```

### 2.4 회원가입 API

```
POST /api/auth/signup
Body: {
  email: string,
  name: string,
  password: string,
  age: number,
  region: Region,
  industry: Industry
}
Response 201: {
  userId: string,
  accessToken: string,
  refreshToken: string
}
Response 409: { error: "EMAIL_TAKEN" }
Response 422: { error: "VALIDATION_ERROR", details: {...} }

GET /api/auth/check-email?email=xxx
Response 200: { available: boolean }

POST /api/auth/login
Body: { email, password }
Response 200: { accessToken, refreshToken, user: UserProfile }
Response 401: { error: "INVALID_CREDENTIALS" }
```

`UserProfile` 응답 필드:

```ts
type UserProfile = {
  id: string;
  email: string;
  name: string;
  age: number;
  region: Region;
  industry: Industry;
};
```

인증 토큰 정책:
- JWT 알고리즘은 `HS256`을 사용하며 비밀키는 `JWT_SECRET` 환경변수로 관리한다.
- access token 기본 만료시간은 30분(`ACCESS_TOKEN_EXPIRE_MINUTES`), refresh token은 14일(`REFRESH_TOKEN_EXPIRE_DAYS`)이다.
- 1차 구현의 refresh token은 DB에 저장하지 않는 stateless JWT이며, 폐기 목록·회전(rotation)·재발급 API는 추후 보안 요구사항 확정 시 추가한다.
- 로그인 실패 시 이메일 존재 여부를 노출하지 않고 `INVALID_CREDENTIALS` 하나로 통일한다.

> 이메일 인증(가입 시 메일 발송/링크 확인) 진행 여부는 미결정 — 섹션 6 참고. 우선은 이메일 형식 검증 + 중복 체크만으로 가입 가능하게 구현하고, 필요 시 `email_verified` 컬럼 추가하는 형태로 확장.

### 2.5 유저 DB 스키마 (PostgreSQL)

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  name VARCHAR(20) NOT NULL,
  password_hash TEXT NOT NULL,
  age INT NOT NULL CHECK (age BETWEEN 18 AND 99),
  region VARCHAR(20) NOT NULL,
  industry VARCHAR(20) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

### 2.6 회원가입 프론트 1차 구현 결정

- 가입 성공 후 access/refresh token은 브라우저 `localStorage`에 각각 `accessToken`, `refreshToken` 키로 저장한다. 운영 보안 검토에서 HttpOnly cookie 방식으로 변경할 수 있다.
- 서버 오류는 사용자용 한국어 문구로 변환한다.
  - `EMAIL_TAKEN`: `이미 사용 중인 이메일이에요.`
  - `VALIDATION_ERROR`: `입력한 정보를 다시 확인해주세요.`
  - 네트워크/기타 오류: `서버에 연결하지 못했어요. 잠시 후 다시 시도해주세요.`
- 가입 성공 후 완료 화면의 `챗봇 시작하기` 버튼으로 `/chat` 경로에 진입한다.

---

## 3. 챗봇 서비스 백엔드 스펙

### 3.1 답변 카테고리 (5개, 고정 — Qdrant payload의 `category` 값과 정확히 일치시킴)

- `visa` 비자
- `departure` 출국준비
- `labor` 노동법
- `tax` 세금
- `life` 생활

챗봇 홈 화면에 이 5개를 **퀵 카테고리 버튼**으로 노출 (자유 질문 입력창 + 카테고리 버튼 병행). 버튼 클릭 시에는 이 값을 그대로 검색 필터로 사용하고, 자유 질문 입력 시에는 GPT-5가 질문을 분석해서 이 5개 중 하나(또는 미해당)로 자동 분류.

### 3.2 전체 파이프라인 (내가 만드는 부분 = 회색 아닌 부분)

**오케스트레이션 방식**: LangGraph 등 그래프 기반 프레임워크는 **사용하지 않음**. 아래 파이프라인이 분기/루프 없는 단순 선형 흐름이라 일반 async 파이썬 함수 체이닝으로 충분함 (섹션 3.5, 3.6 코드 참고). 추후 멀티턴 되묻기, 카테고리별 분기 체인처럼 복잡도가 늘어나면 그때 재검토.

```
[사용자 질문 입력]
      ↓
[백엔드: 질문 전처리 + 사용자 프로필 컨텍스트 결합]
      ↓
[GPT-5: 질문 해석/단일 카테고리 분류 + 영어 Qdrant 검색 쿼리 번역·재작성]  ← 내가 구현
      ↓
[영어 쿼리를 text-embedding-3-small로 임베딩 → Qdrant 벡터 검색 (코사인 유사도)]  ← 내가 구현 (팀원은 임베딩 적재까지만)
      ↓
[GPT-5: 검색된 문서 + 사용자 프로필 기반 답변 생성 + 자체 확신도 평가 (구조화 출력)]  ← 내가 구현
      ↓
[백엔드: 확신도 낮으면 "모르겠다" fallback 메시지로 교체]  ← 내가 구현
      ↓
[프론트: 답변 스트리밍 렌더링]
```

### 3.3 개인화 로직

사용자 프로필(`region`, `industry`, `age`)을 GPT-5 시스템 프롬프트/컨텍스트에 항상 주입.

예시:
- `region=PERTH` 사용자가 "최저시급 얼마야?" 질문 → 검색 쿼리에 WA 주 특이사항 가중치
- `industry=FARM` 사용자가 "세금 신고 어떻게 해?" 질문 → 세컨/서드 비자 조건, 농장 소득 관련 TFN/슈퍼애뉴에이션 맥락 우선 반영

시스템 프롬프트 골격 (예시):

```
당신은 호주 워킹홀리데이 전문 상담 챗봇입니다.
사용자 정보: 나이 {age}세, 거주/예정 지역 {region}, 업종 {industry}
아래 검색된 참고 문서를 근거로만 답변하세요. 문서에 없는 내용은 "확실하지 않다"고 밝히세요.
카테고리: {category}
참고 문서:
{retrieved_chunks}
사용자 질문: {user_query}
```

### 3.4 API 명세

```
POST /api/chat/query
Headers: Authorization: Bearer <accessToken>
Body: {
  message: string,
  category?: "visa" | "departure" | "labor" | "tax" | "life",  // optional, 카테고리 버튼 클릭 시
  conversationId?: string  // 없으면 새 대화 생성
}
Response 200 (SSE 스트리밍 권장): {
  conversationId: string,
  messageId: string,
  answerChunk: string,   // 스트리밍 조각
  sources?: { title: string, url?: string }[]  // 답변 완료 시점에 함께 반환
}

GET /api/chat/conversations
GET /api/chat/conversations/:id/messages
DELETE /api/chat/conversations/:id
```

5-3 API 뼈대 단계의 확정 동작:
- 5-3에서는 일반 JSON 응답을 사용했고, 마일스톤 6부터 `POST /api/chat/query`는 `Content-Type: text/event-stream` SSE 응답을 사용한다.
- 대화·메시지는 1차적으로 인메모리 저장소에 보관하므로 서버 재시작 시 초기화된다. 영구 저장용 DB 스키마는 별도 확정 후 추가한다.
- 인증 실패는 `401 { "error": "UNAUTHORIZED" }`를 반환한다.
- 존재하지 않거나 다른 사용자가 소유한 대화는 정보 노출 방지를 위해 `404 { "error": "CONVERSATION_NOT_FOUND" }`를 반환한다.
- 대화 삭제 성공은 body 없는 `204`를 반환한다.

SSE 이벤트 계약(마일스톤 6 확정):

```text
event: meta
data: {"conversationId":"...","messageId":"..."}

event: chunk
data: {"answerChunk":"답변 조각"}

event: sources
data: {"sources":[{"title":"...","url":"..."}]}

event: done
data: {}
```

- 이벤트 순서는 `meta` → `chunk` 1개 이상 → `sources` → `done`이다.
- GPT-5의 구조화 답변 및 grounded 검증이 끝난 후 검증된 최종 답변만 24자 단위 chunk로 전달한다.
- POST body와 Authorization header가 필요하므로 브라우저 기본 `EventSource` 대신 Fetch API의 `ReadableStream`으로 SSE를 소비한다.
- 응답 헤더에 `Cache-Control: no-cache`, `X-Accel-Buffering: no`를 설정한다.

### 3.5 Qdrant 연동 인터페이스 (확정 스펙)

**역할 분담 재확인**: 팀원은 **임베딩 파이프라인(청킹 → 임베딩 생성 → Qdrant 적재)까지만** 담당. 즉 Qdrant에는 데이터가 이미 들어가 있는 상태이고, **검색 쿼리 실행 로직도, 최종 답변 생성 로직도 전부 내(채은) 담당**. 이전 버전 문서에서 가정했던 "팀원이 만든 내부 검색 서비스 클래스를 호출"하는 구조가 아니라, **`qdrant-client` 라이브러리로 직접 컬렉션에 쿼리를 날리는 코드를 내가 새로 작성**해야 함.

- **컬렉션 이름**: `first_month_guide`
- **Vector size**: 1536
- **Distance**: Cosine
- **Embedding model**: OpenAI `text-embedding-3-small`
- **Qdrant 접속 URL**: 환경변수 `QDRANT_URL`로 관리 (하드코딩 금지). **확정** — 백엔드가 Qdrant와 같은 docker-compose 네트워크 안에 있음 (팀원 compose 파일 확인 완료):
  - 컨테이너 내부(백엔드 `.env`)에서 → `QDRANT_URL=http://qdrant:6333` (compose 서비스 이름 `qdrant` 사용, `container_name: qdrant-db`가 아님에 주의)
  - 호스트에서 직접 스크립트로 확인할 때만 → `http://localhost:6333` (compose에서 포트 노출돼 있음)
  - API 키는 불필요 (compose 파일에 인증 설정 없음)
- **연동 방식**: 별도 AI 서버/외부 API 없음. 백엔드(FastAPI) 프로세스 안에서 `qdrant-client`로 Qdrant 서버(또는 Qdrant Cloud)에 직접 연결해서 검색.
- **BM25 하이브리드 검색**: 팀 결정 — **1차 개발은 dense vector(코사인 유사도) 단일 검색으로 진행.** 팀원이 준 컬렉션 정보(vector size 1536, Cosine, `text-embedding-3-small`)에 sparse vector 언급이 없어 현재 컬렉션엔 BM25용 인덱스가 없을 가능성이 높음. 아래 `check_categories.py` 스크립트로 확정 확인 후, 있으면 하이브리드로 업그레이드, 없으면 재인덱싱 필요 여부를 팀원과 상의 (섹션 6).
- **Python 검색 API**: 현재 프로젝트의 `qdrant-client`에서는 기존 `search()` 대신 `query_points(...).points`를 사용한다. 외부 `search_chunks` 함수 시그니처와 반환 스키마는 그대로 유지한다.
- **장애 응답**: Qdrant URL 누락, 연결 실패 또는 검색 실패 시 `503 { "error": "SEARCH_SERVICE_UNAVAILABLE" }`를 반환한다. OpenAI 임베딩 실패는 섹션 3.7의 `502 AI_SERVICE_UNAVAILABLE`로 처리한다.
- **진단 스크립트**: `backend/scripts/check_categories.py`를 실행해 실제 컬렉션의 vector size/distance, sparse vector, 전체 category 값, 청크 `text` 길이 범위를 읽기 전용으로 확인한다.

**검색 chunk의 payload 스키마 (Qdrant에 이미 적재된 데이터 구조, 실측)**

```json
{
  "id": "visa_417_overview_0",
  "score": 0.82,
  "payload": {
    "country": "호주",
    "country_code": "AU",
    "target_user": "워킹홀리데이",
    "category": "visa",
    "section": "overview",
    "title": "417 비자 개요",
    "chunk_id": "visa_417_overview",
    "chunk_index": 0,
    "chunk_count": 1,
    "source": "https://...",
    "language": "en",
    "last_updated": "2026-07-06",
    "source_path": "knowledge/australia/visa/417_overview.md",
    "original_chunk_id": "visa_417_overview",
    "qdrant_point_id": "…",
    "text": "실제 청크 본문…"
  }
}
```

> `category` 필드는 `visa` / `departure` / `labor` / `tax` / `life` 값으로 payload에 이미 들어있음 (섹션 3.1과 동일하게 확정) → GPT-5 질문 해석 단계에서 뽑은 카테고리와 매칭해서 Qdrant 검색 시 payload 필터로 사용.

> ⚠️ `QDRANT_URL=http://localhost:6333`은 로컬 개발 환경 기준. 팀원 전체가 같은 데이터에 접근하려면 이 Qdrant가 팀원 개인 컴퓨터에서만 떠있는지, 아니면 팀 공유 서버/도커에서 떠있어서 다른 팀원도 접속 가능한지 확인 필요 (섹션 6). 로컬이면 API 키 없이 접속.

**최종 API 응답 목표 스키마 (내가 직접 만들어야 할 출력 형태)**

```json
{
  "answer": "답변 내용",
  "sources": [
    {
      "title": "417 비자 개요",
      "source": "https://...",
      "score": 0.82
    }
  ]
}
```

이 `answer`는 팀원 파이프라인이 주는 게 아니라, **내가 Qdrant 검색 결과(chunk들)를 GPT-5에 근거로 넘겨서 직접 생성**하는 값. `sources`도 검색된 chunk의 `title` / `source` / `score`를 그대로 매핑해서 내가 구성.

**직접 구현할 검색 함수 (Qdrant 클라이언트 직접 호출)**

```python
# backend/rag/qdrant_search.py
import os
from qdrant_client import QdrantClient
from openai import OpenAI

qdrant = QdrantClient(url=os.environ["QDRANT_URL"])  # .env에서 로드, 환경별로 값이 다름 (아래 표 참고)
openai_client = OpenAI()

COLLECTION_NAME = "first_month_guide"

def embed_query(text: str) -> list[float]:
    resp = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return resp.data[0].embedding

def search_chunks(query: str, category: str | None = None, top_k: int = 5) -> list[dict]:
    """
    query를 임베딩해서 Qdrant 컬렉션(first_month_guide)에서 코사인 유사도 검색.
    category가 있으면 payload.category 필터 적용.
    반환: 위 payload 스키마 리스트 (score 포함)
    """
    query_vector = embed_query(query)

    query_filter = None
    if category:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        query_filter = Filter(
            must=[FieldCondition(key="category", match=MatchValue(value=category))]
        )

    results = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        query_filter=query_filter,
        limit=top_k,
    )
    return [
        {"id": r.id, "score": r.score, "payload": r.payload}
        for r in results
    ]
```

```python
# backend/rag/answer_service.py
# 답변 생성 + 자체 검증 로직 포함된 최종 버전은 섹션 3.6 참고
# (build_rag_answer 함수가 여기서 search_chunks() + generate_answer()를 조합함)
```

Codex 작업 전 확정/확인 필요:
- [x] Qdrant 서버 접속 정보 → `http://qdrant:6333` (컨테이너 내부, docker-compose 확인 완료), 호스트에서는 `http://localhost:6333`
- [x] `category` payload 값 전체 목록 → `visa`, `departure`, `labor`, `tax`, `life`
- [x] 백엔드가 팀원 docker-compose에 이미 포함되어 있음 (`./backend` 컨텍스트, `Dockerfile.dev`) → 채은이 만드는 FastAPI 백엔드가 바로 이 서비스
- [ ] sparse vector(BM25)용 인덱스가 컬렉션에 있는지 — 있으면 하이브리드 검색으로 업그레이드
- [ ] 배포(프로덕션) 시 Qdrant URL — 로컬 compose와 동일 구조로 갈지, 별도 클라우드로 옮길지
- [ ] 청크당 `text` 길이 범위 (GPT-5 컨텍스트에 몇 개까지 넣을지 판단 기준)

### 3.6 GPT-5 호출 모듈 (내 담당 핵심 구현)

```python
# backend/chat/query_understanding.py
async def interpret_query(user_message: str, user_profile: dict) -> dict:
    """
    1) 질문의 주된 카테고리 자동 분류 (visa/departure/labor/tax/life 중 하나 또는 None)
    2) 한국어 질문을 영어 공식·법률·행정 문서 검색에 적합한 쿼리로 번역 및 재작성

    반환: {"category": str | None, "search_query_en": str}
    """
    ...
```

```python
# backend/chat/answer_generation.py
import json

VERIFICATION_SYSTEM_PROMPT = """
당신은 호주 워킹홀리데이 전문 상담 챗봇입니다.
사용자 정보: 나이 {age}세, 거주/예정 지역 {region}, 업종 {industry}
카테고리: {category}

아래 참고 문서를 근거로만 답변하세요.
참고 문서:
{retrieved_chunks}

사용자 질문: {user_query}

다음 JSON 형식으로만 답하세요 (다른 텍스트 금지):
{{
  "answer": "답변 내용 (문서에 근거해서 작성)",
  "grounded": true 또는 false,   // 참고 문서만으로 이 질문에 확실히 답할 수 있으면 true
  "confidence": "high" | "medium" | "low"
}}

주의:
- 참고 문서에 명확한 근거가 없으면 "grounded": false, "confidence": "low"로 표시하세요.
- 문서 내용을 추측하거나 지어내지 마세요. 모르면 모른다고 판단하는 것이 최우선입니다.
"""

FALLBACK_MESSAGE = (
    "죄송해요, 지금 갖고 있는 정보만으로는 확실하게 답변드리기 어려워요. "
    "호주 이민성 공식 사이트(https://immi.homeaffairs.gov.au)나 관련 기관에 "
    "직접 확인해보시는 걸 추천드려요. 질문을 조금 더 구체적으로 해주시면 다시 찾아볼게요!"
)

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
    prompt = VERIFICATION_SYSTEM_PROMPT.format(
        age=user_profile["age"],
        region=user_profile["region"],
        industry=user_profile["industry"],
        category=category or "미분류",
        retrieved_chunks="\n\n".join(c["payload"]["text"] for c in retrieved_chunks),
        user_query=user_message,
    )

    # GPT-5 호출 (response_format으로 JSON 강제 권장)
    response = await call_gpt5(prompt, response_format="json")
    result = json.loads(response)

    is_low_confidence = (
        not result.get("grounded", False)
        or result.get("confidence") == "low"
        or not retrieved_chunks  # 검색 결과 자체가 없는 경우도 fallback
    )

    if is_low_confidence:
        return {"answer": FALLBACK_MESSAGE, "grounded": False, "confidence": "low"}

    return result
```

```python
# backend/rag/answer_service.py
async def build_rag_answer(user_message: str, user_profile: dict, category: str | None) -> dict:
    """
    1) search_chunks()로 Qdrant 검색
    2) generate_answer()로 답변 생성 + 자체 검증 (grounded 판단 포함)
    3) {"answer": str, "sources": [...]} 형태로 리턴
       - fallback("모르겠다")인 경우 sources는 빈 배열로 반환 (근거 없다고 판단했으므로)
    """
    chunks = search_chunks(user_message, category=category, top_k=5)
    result = await generate_answer(user_message, chunks, user_profile, category)

    if not result["grounded"]:
        return {"answer": result["answer"], "sources": []}

    sources = [
        {
            "title": c["payload"]["title"],
            "source": c["payload"]["source"],
            "score": c["score"],
        }
        for c in chunks
    ]
    return {"answer": result["answer"], "sources": sources}
```

### 3.7 GPT-5 호출 및 오류 처리 확정 사항

- OpenAI 호출은 Responses API의 구조화 출력(Pydantic schema)을 사용한다.
- API 키는 `OPENAI_API_KEY`, 모델명은 `OPENAI_MODEL` 환경변수로 관리하며 기본 모델은 스펙에 지정된 `gpt-5`다.
- OpenAI 호출 실패 또는 구조화된 출력 부재 시 `502 { "error": "AI_SERVICE_UNAVAILABLE" }`를 반환한다.
- 질문 해석 결과의 주된 단일 카테고리로 검색하고 score 내림차순 상위 5개를 답변 생성에 사용한다.
- 사용자가 카테고리 버튼으로 값을 명시하면 해당 카테고리를 우선 사용한다.
- 검색 결과가 없거나 `grounded=false` 또는 `confidence=low`이면 섹션 3.6의 fallback 문구와 빈 `sources`를 반환한다.
- Qdrant의 `payload.text`와 적재 임베딩은 영어 기준이다. 검색 직전 `search_query_en`만 임베딩하며 한국어 원문을 검색 벡터 입력에 다시 혼합하지 않는다.
- 답변 생성은 영어 참고 문서의 의미와 근거를 판단한 뒤 영어 원문을 그대로 붙여넣지 않고 자연스러운 한국어로 재구성한다.
- 질문 해석 결과는 주된 단일 카테고리를 사용한다. 사용자가 카테고리 버튼으로 값을 명시하면 그 값을 우선한다.

---

## 4. 프론트엔드 디자인 방향

### 4.1 톤앤매너 목표

**토스(신뢰감 있는 심플함) + 애플(여백/타이포그래피) + 메타(생동감 있는 컬러 포인트)** 를 참고하되, 특정 브랜드 카피가 아니라 워홀이라는 주제에 맞는 독자적인 아이덴티티로 재해석.

차별화 포인트 제안:
- 토스처럼 무채색 베이스는 가져가되, **포인트 컬러는 호주를 연상시키는 톤**(예: 선셋 오렌지 + 딥 블루/오션 계열) 조합으로 차별화
- 메타처럼 그라디언트/생동감을 쓰되 과하지 않게, 카드형 UI의 그림자/라운드 코너 정도로만 활용
- 애플처럼 큰 타이포 + 넉넉한 여백, 단 폰트는 Pretendard 등 한글 가독성 좋은 폰트 사용

### 4.2 핵심 화면 리스트

1. 온보딩/스플래시
2. 회원가입 (스텝형, 섹션 2 참고)
3. 로그인
4. 홈 (프로필 요약 + 5개 카테고리 카드 + 최근 대화)
5. 챗봇 대화 화면 (말풍선 + 스트리밍 타이핑 효과 + 출처 카드)
6. 마이페이지 (프로필 수정, 지역/업종 변경)

### 4.3 디자인 시스템 기본값 (Codex가 바로 쓸 수 있는 토큰)

```css
:root {
  --color-bg: #FAFAFA;
  --color-surface: #FFFFFF;
  --color-text-primary: #1A1A1A;
  --color-text-secondary: #6B6B6B;
  --color-primary: #FF6B35;    /* 선셋 오렌지 - 포인트 */
  --color-secondary: #0B3D91;  /* 딥 오션 블루 */
  --color-border: #EAEAEA;
  --radius-card: 20px;
  --radius-button: 14px;
  --radius-pill: 999px;
  --shadow-card: 0 4px 20px rgba(0, 0, 0, 0.06);
  --shadow-button: 0 4px 12px rgba(0, 0, 0, 0.08);
  --shadow-button-active: 0 2px 6px rgba(0, 0, 0, 0.05);
  --space-1: 8px;
  --space-2: 16px;
  --space-3: 24px;
  --space-4: 32px;
  --space-6: 48px;
  --font-family: "Pretendard", -apple-system, sans-serif;
}
```

- 버튼: 풀-바운드(pill) 대신 살짝 둥근 사각형(radius 14~20px) — 토스 느낌
- 카드: 그림자는 얇고 넓게 (`box-shadow: 0 4px 20px rgba(0,0,0,0.06)`)
- 인터랙션: 버튼 탭 시 살짝 스케일 다운(0.97) 애니메이션 — 애플/메타 특유의 탄성감
- 반응형 기준: 모바일 `30rem(480px)` 이하, 태블릿 `48rem(768px)` 이하, 소형 데스크톱 `64rem(1024px)` 이하에서 단계적으로 레이아웃을 전환한다.
- 모바일 버튼/인풋 등 조작 요소는 최소 `44px × 44px` 터치 영역을 확보하고, 문서 루트에서 의도하지 않은 가로 스크롤이 발생하지 않게 한다.
- 한글 제목·본문·버튼 라벨은 어절 중간에서 끊기지 않도록 전역에 `word-break: keep-all`과 긴 문자열 안전장치인 `overflow-wrap: break-word`를 적용한다.

프론트 작업 시작 전 `frontend-design` 관련 세부 가이드는 별도로 로드해서 확인할 것 (Codex 환경에 따라 다를 수 있음).

### 4.4 챗봇 프론트 1차 구현 결정

- `/chat`은 access token이 필요한 보호 경로이며 토큰이 없거나 API가 `401`을 반환하면 토큰을 제거하고 `/signup`으로 이동한다.
- 회원가입 완료 후 `챗봇 시작하기` 버튼으로 `/chat`에 진입한다.
- 첫 화면은 자유 질문 입력과 `visa`/`departure`/`labor`/`tax`/`life` 퀵 카테고리를 함께 표시한다.
- 대화 화면은 사용자/AI 말풍선, 스트리밍 타이핑 표시, 출처 링크 카드, 최근 대화 조회·선택·삭제, 새 대화, 로그아웃을 제공한다.
- 질문 입력은 Enter로 전송하고 Shift+Enter로 줄바꿈한다. 전송 중에는 중복 요청을 방지한다.
- 모바일에서는 최근 대화 사이드바를 오버레이 방식으로 열고 닫는다.
- `SEARCH_SERVICE_UNAVAILABLE`은 검색 서비스 연결 오류로 안내하고, 그 밖의 AI/네트워크 오류는 일반 답변 실패 문구로 표시한다.

---

## 5. 개발 우선순위 (마일스톤)

| 순서 | 작업 | 비고 |
|---|---|---|
| 1 | 유저 DB 스키마 + 회원가입/로그인 API | 인증 없으면 나머지 다 막힘 |
| 2 | 회원가입 프론트 (스텝 폼) | 디자인 시스템 토큰 먼저 확정 후 진행 |
| 3 | 챗봇 API 뼈대 (Qdrant 목업 연동) | 팀원 실제 연동 전까지 목업 데이터로 개발 |
| 4 | GPT-5 질문해석/답변생성 모듈 | 프롬프트 튜닝 반복 필요 |
| 5 | Qdrant 실제 연동 | 팀원 스펙 확정되는 대로 |
| 6 | 챗봇 프론트 (스트리밍 UI) | |
| 7 | 마이페이지, 폴리싱 | |

---

## 6. 확인 필요 사항 (Open Questions)

- [ ] 이메일 인증(가입 시 메일 발송/링크 확인) 진행 여부: X
- [ ] sparse vector(BM25)용 인덱스가 컬렉션에 있는지 여부 (없으면 dense 검색만으로 1차 구현): X
- [ ] 배포 시 Qdrant를 어떤 방식으로 접근할지 (로컬 compose와 동일 구조 유지 vs 별도 서버/클라우드): 아직 모름
- [ ] 로컬 `qdrant_data` 볼륨에 `first_month_guide` 컬렉션을 적재하거나 팀 데이터 볼륨을 연결할지 확인 (2026-07-12 실측: 현재 컬렉션 목록 `[]`)
- [x] GPT-5 API 키/엔드포인트 관리 방식 → dotenv 환경변수(`OPENAI_API_KEY`, `OPENAI_MODEL`) 사용
- [x] `backend`에 `depends_on: qdrant` 추가 → `service_started` 조건 적용
- [x] 1차 카테고리 태그 범위 → 추가 세분화 없이 ["visa", "departure", "labor", "tax", "life"] 5개 고정
