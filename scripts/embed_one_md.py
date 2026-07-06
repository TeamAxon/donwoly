from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from src.chunkers.text_chunker import TextChunker  # noqa: E402
from src.parsers.markdown_parser import MarkdownParser  # noqa: E402
from src.services.embedding_service import EmbeddingService  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage:")
        print("  python scripts/embed_one_md.py <markdown-file-path>")
        return 1

    path = Path(sys.argv[1])

    try:
        parsed = MarkdownParser().parse(path)
        chunks = TextChunker().split(parsed)
        embedded_chunks = EmbeddingService().embed_chunks(chunks)
    except Exception as exc:
        print("[error]")
        print(exc)
        return 1

    print(f"Parsed markdown: {parsed.metadata.get('title')}")
    print(f"Created chunks: {len(chunks)}")

    for embedded_chunk in embedded_chunks:
        print(f"Embedded chunk: {embedded_chunk.id}")
        print(f"Title: {embedded_chunk.metadata.get('title')}")
        print(f"Vector dimension: {len(embedded_chunk.vector)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
