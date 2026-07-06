# Qdrant Scripts

Qdrant 벡터DB를 확인하고, Markdown 지식을 적재하고, 검색 테스트를 수행하는 스크립트를 두는 폴더입니다.

현재 단계:

0. DB 스크립트용 패키지 설치

   ```bash
   python3 -m pip install -r scripts/qdrant/requirements.txt
   ```

1. `01_check_qdrant.py`
   - Python에서 Qdrant에 연결되는지 확인합니다.
   - `first_month_guide` Collection이 있는지 확인합니다.

다음 단계에서 추가할 예정:

2. `02_create_collection.py`
   - `first_month_guide` Collection을 생성합니다.
   - vector size는 `1536`, metric은 `Cosine`을 사용합니다.

   ```bash
   python3 scripts/qdrant/02_create_collection.py
   ```

3. `03_load_markdown.py`
   - `data/knowledge` 아래 Markdown 파일을 읽습니다.
   - frontmatter를 payload로 변환합니다.

4. `04_embed_and_upsert.py`
   - OpenAI `text-embedding-3-small`로 embedding을 생성합니다.
   - Qdrant에 vector와 payload를 저장합니다.

5. `05_search_test.py`
   - 사용자 질문을 embedding합니다.
   - Qdrant에서 유사 문서를 검색합니다.
