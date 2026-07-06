from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from config.settings import COLLECTION_NAME, QDRANT_URL  # noqa: E402
from src.chunkers.text_chunker import TextChunker  # noqa: E402
from src.parsers.markdown_parser import MarkdownParser  # noqa: E402
from src.services.embedding_service import EmbeddingService  # noqa: E402
from src.services.qdrant_service import QdrantService  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage:")
        print("  python scripts/ingest_one_md.py <markdown-file-path>")
        return 1

    load_dotenv()

    qdrant_url = os.getenv("QDRANT_URL", QDRANT_URL)
    collection_name = os.getenv("QDRANT_COLLECTION", COLLECTION_NAME)

    try:
        parsed = MarkdownParser().parse(Path(sys.argv[1]))
        chunks = TextChunker().split(parsed)
        embedded_chunks = EmbeddingService().embed_chunks(chunks)

        qdrant = QdrantService(url=qdrant_url, collection_name=collection_name)
        qdrant.ensure_collection()
        qdrant.upsert_chunks(embedded_chunks)
    except Exception as exc:
        print("[error]")
        print(exc)
        return 1

    print(f"Parsed markdown: {parsed.metadata.get('title')}")
    print(f"Created chunks: {len(chunks)}")
    print(f"Embedded chunks: {len(embedded_chunks)}")
    print(f"Qdrant collection ready: {collection_name}")
    print(f"Upserted points: {len(embedded_chunks)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
