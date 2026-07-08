# 첫달가이드 DB/RAG 파이프라인

외교부 공공데이터 기반 AI 서비스 **첫달가이드**의 지식 문서 관리, 임베딩 생성, Qdrant 적재, RAG 답변 테스트용 작업 공간입니다.

현재 MVP 범위는 **호주 워킹홀리데이**입니다.

## 1. 전체 흐름

```text
Markdown 지식 문서
↓
YAML Front Matter 파싱
↓
본문 텍스트 chunk 분리
↓
OpenAI text-embedding-3-small 임베딩 생성
↓
Qdrant first_month_guide Collection에 upsert
↓
사용자 질문 임베딩
↓
Qdrant 유사 문서 검색
↓
검색된 문서를 근거로 GPT 답변 생성
```

## 2. 폴더 구조

```text
knowledge/
└─ australia/
   ├─ visa/
   ├─ departure/
   ├─ labor_law/
   ├─ tax/
   └─ life/

src/
├─ parsers/
│  └─ markdown_parser.py
├─ chunkers/
│  └─ text_chunker.py
└─ services/
   ├─ embedding_service.py
   ├─ qdrant_service.py
   └─ rag_service.py

scripts/
├─ parse_markdown.py
├─ chunk_markdown.py
├─ generate_mofa_entry_md.py
├─ run_mofa_entry_pipeline.py
├─ embed_one_md.py
├─ ingest_one_md.py
├─ ingest_all_md.py
├─ search_qdrant.py
└─ ask_rag.py
```

## 3. category 값

| category | 의미 |
|---|---|
| `visa` | 비자 정보 |
| `departure` | 출국 준비 |
| `labor_law` | 노동법/근로권 |
| `tax` | 세금 |
| `life` | 현지 생활 |

## 4. Markdown 문서 형식

각 지식 문서는 YAML Front Matter와 본문으로 구성합니다.

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

# 본문 제목

본문 내용...
```

Front Matter는 Qdrant payload가 되고, 본문은 embedding 대상이 됩니다.

## 5. 환경 준비

Python 패키지를 설치합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

`.env.example`을 복사해서 `.env`를 만듭니다.

```bash
cp .env.example .env
```

`.env`에는 아래 값이 필요합니다.

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4o-mini
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=first_month_guide
```

`.env`는 GitHub에 올리지 않습니다.

## 6. 실행 순서

### 1) Qdrant Docker 실행 확인

Qdrant만 실행합니다.

```bash
docker compose up -d qdrant
```

실행 상태 확인:

```bash
docker compose ps
curl http://localhost:6333/collections
```

브라우저에서는 아래 주소로 확인할 수 있습니다.

```text
http://localhost:6333/dashboard
```

Docker 권한 오류가 나면 Docker Desktop을 먼저 실행한 뒤 다시 시도합니다.

### 2) .env 설정

```bash
cp .env.example .env
```

`.env`의 `OPENAI_API_KEY`를 실제 키로 바꿉니다.

### 3) md 파일 파싱 테스트

```bash
python scripts/parse_markdown.py knowledge/australia/visa/417_overview.md
```

확인할 것:

- metadata가 출력되는지
- content preview가 출력되는지
- Front Matter 필수값 오류가 없는지

### 4) chunk 테스트

```bash
python scripts/chunk_markdown.py knowledge/australia/visa/417_overview.md
```

확인할 것:

- chunk 수가 출력되는지
- `qdrant_point_id`가 생성되는지
- title, category, text preview가 출력되는지

### 5) embedding 테스트

```bash
python scripts/embed_one_md.py knowledge/australia/visa/417_overview.md
```

확인할 것:

- `Vector dimension: 1536`이 출력되는지
- `OPENAI_API_KEY` 오류가 없는지

### 6) Qdrant 단일 md 적재

```bash
python scripts/ingest_one_md.py knowledge/australia/visa/417_overview.md
```

확인할 것:

- `Qdrant collection ready: first_month_guide`
- `Upserted points: 1`

같은 문서를 다시 적재하면 같은 point id로 덮어씁니다.

### 7) 전체 md 적재

먼저 dry-run으로 문서 파싱과 chunk만 확인합니다.

```bash
python scripts/ingest_all_md.py --dry-run
python scripts/ingest_all_md.py knowledge/australia --dry-run
```

문제가 없으면 실제로 Qdrant에 적재합니다.

```bash
python scripts/ingest_all_md.py
python scripts/ingest_all_md.py knowledge/australia
```

확인할 것:

- 전체 md 파일 수
- 성공/실패 파일 수
- 생성된 chunk 수
- upsert된 point 수
- 실패 파일과 에러 메시지

### 8) Qdrant 검색 테스트

```bash
python scripts/search_qdrant.py "417 비자가 뭐야?"
```

확인할 것:

- score가 출력되는지
- title, category, text preview가 출력되는지
- 검색 결과가 417 비자 문서와 관련 있는지

### 9) RAG 답변 테스트

```bash
python scripts/ask_rag.py "417 비자가 뭐야?"
```

확인할 것:

- 답변에 검색된 문서 내용이 반영되는지
- Sources에 title, source, score가 출력되는지
- 답변이 제공된 context 밖의 내용을 단정하지 않는지

## 7. 스크립트 역할

| 파일 | 역할 |
|---|---|
| `scripts/parse_markdown.py` | md 파일의 Front Matter와 본문 분리 테스트 |
| `scripts/chunk_markdown.py` | 본문을 Qdrant 검색용 chunk로 분리 테스트 |
| `scripts/generate_mofa_entry_md.py` | 외교부 국가·지역별 입국허가요건 CSV/JSON에서 호주 md 자동 생성 |
| `scripts/run_mofa_entry_pipeline.py` | 외교부 원본 데이터 탐색, md 생성, 검증, dry-run을 한 번에 실행 |
| `scripts/embed_one_md.py` | chunk를 OpenAI embedding vector로 변환 테스트 |
| `scripts/ingest_one_md.py` | md 파일 1개를 Qdrant에 적재 |
| `scripts/ingest_all_md.py` | knowledge 폴더 전체 md를 Qdrant에 적재 |
| `scripts/search_qdrant.py` | 사용자 질문으로 Qdrant 검색 테스트 |
| `scripts/ask_rag.py` | Qdrant 검색 결과를 근거로 GPT 답변 생성 |

## 8. 공공데이터 → Markdown 자동 생성

외교부 공공데이터 원본 CSV 또는 JSON은 `data/raw/` 폴더에 둡니다.

```text
data/
└─ raw/
   └─ mofa_entry_requirement.csv
```

파일명 예시:

```text
data/raw/mofa_entry_requirement.csv
data/raw/mofa_entry_requirement.json
```

한 번에 실행:

```bash
python scripts/run_mofa_entry_pipeline.py \
  --source-url "공식 데이터 URL" \
  --last-updated 2026-07-07
```

이 명령은 아래 순서만 실행합니다.

```text
data/raw 원본 탐색
↓
Markdown 자동 생성
↓
생성 파일 확인
↓
validate_generated_md.py 검증
↓
ingest_all_md.py --dry-run
```

실제 Qdrant 적재는 실행하지 않습니다.

호주 입국허가요건 Markdown 자동 생성:

```bash
python scripts/generate_mofa_entry_md.py data/raw/mofa_entry_requirement.csv \
  --source-url "공식 데이터 URL" \
  --last-updated 2026-07-07
```

입력 파일을 생략하면 `data/raw/` 아래 첫 번째 `.csv` 또는 `.json` 파일을 읽습니다.

```bash
python scripts/generate_mofa_entry_md.py
```

생성 파일:

```text
knowledge/australia/visa/mofa_entry_requirement.md
```

검증 명령어:

```bash
python scripts/validate_generated_md.py
```

dry-run 명령어:

```bash
python scripts/ingest_all_md.py knowledge/australia --dry-run
```

## 9. 자주 나는 오류

### `ModuleNotFoundError: No module named 'yaml'`

패키지가 설치되지 않은 Python으로 실행한 경우입니다.

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### `OPENAI_API_KEY is missing`

`.env`에 실제 OpenAI API Key가 없습니다.

### `Couldn't connect to server` 또는 Qdrant 연결 오류

Qdrant가 실행 중인지 확인합니다.

```bash
docker compose up -d qdrant
curl http://localhost:6333/collections
```

### Docker permission 오류

Docker Desktop을 먼저 실행한 뒤 다시 시도합니다.
