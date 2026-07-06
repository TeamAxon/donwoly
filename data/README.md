# Data

RAG에 사용할 지식 데이터를 관리하는 폴더입니다.

## 폴더 구조

- `knowledge/`
  - Notion에서 export한 Markdown 원본을 정리해서 보관합니다.
  - 현재는 호주 워킹홀리데이 비자 샘플 문서가 들어 있습니다.

- `processed/`
  - Markdown을 chunk로 변환한 결과를 저장할 폴더입니다.
  - 예: `chunks.jsonl`

## Markdown 작성 규칙

각 Markdown 파일은 Qdrant payload로 사용할 frontmatter를 맨 위에 둡니다.

```md
---
chunk_id: visa_417_overview
title: 417 비자 개요
country: Australia
city: all
category: visa
subcategory: overview
source: Australian Department of Home Affairs
url: https://...
importance: 필수
status: ready
---
```

`status` 값은 아래처럼 사용합니다.

- `ready`: Qdrant에 적재 가능한 문서
- `draft`: 아직 본문 보완이 필요한 문서
