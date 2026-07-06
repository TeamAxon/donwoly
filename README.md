# 첫달가이드

외교부 공공데이터 기반 AI 서비스 **첫달가이드**의 DB/RAG 데이터 파이프라인 작업 공간입니다.

이 프로젝트는 어학연수·워킹홀리데이 청년이 해외 첫 달에 필요한 정보를 쉽게 찾도록 돕는 서비스를 목표로 합니다. 현재는 MVP 범위를 **호주 워킹홀리데이**로 좁혀 시작합니다.

## 1. 프로젝트 설명

첫달가이드는 Markdown으로 정리한 지식 문서를 기반으로 RAG 검색을 수행하는 AI 서비스입니다.

데이터 흐름은 다음과 같습니다.

```text
Markdown 지식 문서
↓
YAML Front Matter 파싱
↓
본문 텍스트 추출
↓
OpenAI text-embedding-3-small 임베딩 생성
↓
Qdrant first_month_guide Collection에 upsert
↓
사용자 질문과 의미가 가까운 문서 검색
↓
검색 문서를 LLM 답변 근거로 사용
```

이번 단계에서는 실제 OpenAI API나 Qdrant 연결 코드를 작성하지 않고, 지식 문서 구조와 작성 표준만 먼저 정리합니다.

## 2. knowledge 폴더 구조

`knowledge/`는 RAG에 사용할 원본 Markdown 지식 문서를 보관하는 폴더입니다.

```text
knowledge/
└─ australia/
   ├─ visa/
   ├─ departure/
   ├─ labor_law/
   ├─ tax/
   └─ life/
```

국가별로 폴더를 나누고, 그 아래에 카테고리 폴더를 둡니다. 현재는 호주만 만들지만, 나중에는 아래처럼 확장할 수 있습니다.

```text
knowledge/
├─ australia/
├─ canada/
└─ japan/
```

## 3. category 값 설명

Qdrant payload의 `category` 값은 아래 중 하나를 사용합니다.

| category | 의미 | 예시 |
|---|---|---|
| `visa` | 비자 정보 | 417 비자 개요, 신청 자격, 신청 절차 |
| `departure` | 출국 준비 | 여권, 보험, 항공권, 준비물 |
| `labor_law` | 노동법/근로권 | 최저임금, 계약, 임금 미지급, 부당 공제 |
| `tax` | 세금 | TFN, 세금 신고, superannuation |
| `life` | 현지 생활 | 숙소, 은행, 교통, 통신, 의료 |

카테고리를 통일하는 이유는 Qdrant 검색 시 필터로 사용할 수 있기 때문입니다. 예를 들어 사용자가 비자 질문을 하면 `category: visa` 문서 위주로 검색할 수 있습니다.

## 4. YAML Front Matter란?

Markdown 파일 맨 위에 `---`로 감싼 메타데이터 영역입니다.

```md
---
country: 호주
country_code: AU
target_user: 워킹홀리데이
category: visa
section: overview
title: 417 비자 개요
chunk_id: visa_417_overview
source: https://...
language: ko
last_updated: 2026-07-06
---
```

이 영역은 임베딩 대상이 아니라, Qdrant payload로 저장할 메타데이터입니다.

## 5. Qdrant payload로 들어가는 정보

Qdrant에는 Markdown 파일 자체가 저장되지 않습니다.

실제로 저장되는 것은 아래 두 가지입니다.

```text
1. 본문 텍스트를 임베딩한 1536차원 벡터
2. Front Matter에서 추출한 payload
```

payload 예시는 다음과 같습니다.

```json
{
  "country": "호주",
  "country_code": "AU",
  "target_user": "워킹홀리데이",
  "category": "visa",
  "section": "overview",
  "title": "417 비자 개요",
  "chunk_id": "visa_417_overview",
  "source": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/work-holiday-417",
  "language": "ko",
  "last_updated": "2026-07-06"
}
```

payload를 넣는 이유는 출처 표시, 카테고리 필터링, 국가별 확장, 문서 추적을 쉽게 하기 위해서입니다.

## 6. 앞으로 ingest 스크립트가 할 일

향후 `scripts/` 폴더의 스크립트는 아래 순서로 동작하게 됩니다.

1. `knowledge/` 아래의 `.md` 파일 읽기
2. YAML Front Matter 파싱
3. Markdown 본문 추출
4. OpenAI `text-embedding-3-small`로 임베딩 생성
5. Qdrant `first_month_guide` Collection에 vector와 payload upsert

현재 단계에서는 실제 연결 코드를 작성하지 않고, 각 스크립트 파일에 역할만 정의해둡니다.

## 7. Markdown Parser

`src/parsers/markdown_parser.py`는 Markdown 지식 문서를 RAG 파이프라인이 사용할 수 있는 형태로 읽는 파서입니다.

파서가 분리하는 값은 세 가지입니다.

| 값 | 역할 |
|---|---|
| `metadata` | YAML Front Matter를 dict로 변환한 값입니다. 나중에 Qdrant payload가 됩니다. |
| `content` | Front Matter를 제외한 Markdown 본문입니다. 나중에 embedding 대상이 됩니다. |
| `source_path` | 원본 파일 경로입니다. Qdrant 검색 결과가 어떤 md 파일에서 왔는지 추적하고 디버깅할 때 필요합니다. |

필수 메타데이터 검증을 하는 이유는, 나중에 md 파일이 수십~수백 개로 늘어났을 때 잘못 작성된 문서가 Qdrant에 들어가는 것을 막기 위해서입니다.

필수 필드:

```text
country
country_code
target_user
category
title
chunk_id
source
language
last_updated
```

허용되는 `category` 값:

```text
visa
departure
labor_law
tax
life
```

실행 예시:

```bash
python3 -m pip install -r requirements.txt
python3 scripts/parse_markdown.py knowledge/australia/visa/417_overview.md
```

정상 실행 시 metadata, source_path, content preview가 출력됩니다.

## 8. Text Chunker

`src/chunkers/text_chunker.py`는 긴 Markdown 본문을 Qdrant 검색에 적합한 작은 단위로 나눕니다.

- `Chunk.text`: 나중에 embedding 대상이 되는 텍스트입니다.
- `Chunk.metadata`: Qdrant payload의 기반이 되는 메타데이터입니다.
- `source_path`, `chunk_index`, `chunk_count`, `original_chunk_id`, `qdrant_point_id`를 metadata에 추가합니다.

실행 예시:

```bash
python3 scripts/chunk_markdown.py knowledge/australia/visa/417_overview.md
```

이번 단계에서는 OpenAI Embedding 생성이나 Qdrant 저장은 하지 않습니다.

## 9. Embedding Service

`src/services/embedding_service.py`는 chunk의 `text`를 OpenAI `text-embedding-3-small` 모델로 임베딩합니다.

- 입력: `Chunk.text`
- 출력: 1536차원 `list[float]`
- 보존: `Chunk.metadata`는 나중에 Qdrant payload로 쓰기 위해 그대로 유지합니다.

실행 전 `.env`에 `OPENAI_API_KEY`가 필요합니다.

```bash
python3 -m pip install -r requirements.txt
python3 scripts/embed_one_md.py knowledge/australia/visa/417_overview.md
```

이번 단계에서는 Qdrant 저장은 하지 않고, chunk별 vector dimension이 `1536`인지 확인합니다.

## 10. Qdrant Service

`src/services/qdrant_service.py`는 임베딩된 chunk를 Qdrant에 저장하고 검색하는 서비스입니다.

- Collection: `first_month_guide`
- Vector size: `1536`
- Distance: `Cosine`
- Payload: chunk metadata 전체 + `text`

문서 하나 적재:

```bash
python3 scripts/ingest_one_md.py knowledge/australia/visa/417_overview.md
```

검색 테스트:

```bash
python3 scripts/search_qdrant.py "417 비자가 뭐야?"
```

이번 단계에서는 검색 결과를 출력하기만 하며, GPT 답변 생성은 하지 않습니다.

여러 Markdown 문서 한 번에 점검:

```bash
python3 scripts/ingest_all_md.py --dry-run
python3 scripts/ingest_all_md.py knowledge/australia --dry-run
```

여러 Markdown 문서 한 번에 Qdrant 적재:

```bash
python3 scripts/ingest_all_md.py
python3 scripts/ingest_all_md.py knowledge/australia
```

`--dry-run`은 OpenAI 임베딩과 Qdrant 저장을 하지 않고, 파일 파싱과 청킹 결과만 확인합니다.

## 11. RAG Service

`src/services/rag_service.py`는 사용자 질문을 임베딩하고, Qdrant에서 관련 chunk를 검색한 뒤, 검색된 context만 근거로 GPT 답변을 생성합니다.

흐름:

```text
질문
↓
EmbeddingService
↓
QdrantService.search
↓
검색된 chunk text를 context로 구성
↓
GPT 답변 생성
```

실행 예시:

```bash
python3 scripts/ask_rag.py "417 비자가 뭐야?"
```

답변은 제공된 context 안에서만 생성하도록 제한하며, 비자/법률 최종 판단을 단정하지 않도록 프롬프트에 명시합니다.
