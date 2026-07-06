from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from config.settings import COLLECTION_NAME, QDRANT_URL  # noqa: E402
from src.services.embedding_service import EmbeddingService  # noqa: E402
from src.services.qdrant_service import QdrantService  # noqa: E402


def preview(text: str, max_chars: int = 180) -> str:
    compact = " ".join(text.strip().split())
    if len(compact) > max_chars:
        return compact[:max_chars].rstrip() + "..."
    return compact


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage:")
        print('  python scripts/search_qdrant.py "417 비자가 뭐야?"')
        return 1

    load_dotenv()

    query = " ".join(sys.argv[1:]).strip()
    qdrant_url = os.getenv("QDRANT_URL", QDRANT_URL)
    collection_name = os.getenv("QDRANT_COLLECTION", COLLECTION_NAME)

    try:
        query_vector = EmbeddingService().embed_text(query)
        qdrant = QdrantService(url=qdrant_url, collection_name=collection_name)
        results = qdrant.search(query_vector=query_vector, limit=5)
    except Exception as exc:
        print("[error]")
        print(exc)
        return 1

    for index, result in enumerate(results, start=1):
        payload = result.payload or {}

        print(f"Top {index}")
        print(f"score: {result.score}")
        print(f"title: {payload.get('title')}")
        print(f"category: {payload.get('category')}")
        print(f"text preview: {preview(payload.get('text', ''))}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
