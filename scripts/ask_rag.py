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
from src.services.rag_service import RAGService  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage:")
        print('  python scripts/ask_rag.py "417 비자가 뭐야?"')
        return 1

    load_dotenv()

    question = " ".join(sys.argv[1:]).strip()
    qdrant_url = os.getenv("QDRANT_URL", QDRANT_URL)
    collection_name = os.getenv("QDRANT_COLLECTION", COLLECTION_NAME)

    try:
        embedding_service = EmbeddingService()
        qdrant_service = QdrantService(
            url=qdrant_url,
            collection_name=collection_name,
        )
        rag_service = RAGService(
            embedding_service=embedding_service,
            qdrant_service=qdrant_service,
        )
        result = rag_service.answer(question, limit=3)
    except Exception as exc:
        print("[error]")
        print(exc)
        return 1

    print("[Answer]")
    print(result["answer"])

    print()
    print("[Sources]")
    for index, source in enumerate(result["sources"], start=1):
        print(f"{index}. {source['title']} - score: {source['score']}")
        print(f"   source: {source['source']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
