from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from src.chunkers.text_chunker import TextChunker  # noqa: E402
from src.parsers.markdown_parser import MarkdownParser  # noqa: E402


def preview(text: str, max_chars: int = 160) -> str:
    compact = " ".join(text.strip().split())
    if len(compact) > max_chars:
        return compact[:max_chars].rstrip() + "..."
    return compact


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage:")
        print("  python scripts/chunk_markdown.py <markdown-file-path>")
        return 1

    path = Path(sys.argv[1])
    parser = MarkdownParser()
    chunker = TextChunker()

    try:
        parsed = parser.parse(path)
        chunks = chunker.split(parsed)
    except Exception as exc:
        print("[error]")
        print(exc)
        return 1

    print(f"총 chunk 수: {len(chunks)}")

    for index, chunk in enumerate(chunks):
        print()
        print(f"[Chunk {index}]")
        print(f"id: {chunk.id}")
        print(f"title: {chunk.metadata.get('title')}")
        print(f"category: {chunk.metadata.get('category')}")
        print(f"qdrant_point_id: {chunk.metadata.get('qdrant_point_id')}")
        print(f"text preview: {preview(chunk.text)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
