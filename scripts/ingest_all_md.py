from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from config.settings import COLLECTION_NAME, KNOWLEDGE_DIR, QDRANT_URL  # noqa: E402
from src.chunkers.text_chunker import TextChunker  # noqa: E402
from src.parsers.markdown_parser import MarkdownParser  # noqa: E402


@dataclass
class IngestSummary:
    total_files: int = 0
    success_files: int = 0
    failed_files: int = 0
    generated_chunks: int = 0
    upserted_points: int = 0
    failures: list[tuple[Path, str]] = field(default_factory=list)


def find_markdown_files(target_dir: Path) -> list[Path]:
    if not target_dir.exists():
        raise FileNotFoundError(f"Target directory does not exist: {target_dir}")
    if not target_dir.is_dir():
        raise NotADirectoryError(f"Target path is not a directory: {target_dir}")

    ignored_names = {"README.md", ".gitkeep"}
    return sorted(
        path
        for path in target_dir.rglob("*.md")
        if path.name not in ignored_names
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest all Markdown knowledge files into Qdrant."
    )
    parser.add_argument(
        "target_dir",
        nargs="?",
        default=KNOWLEDGE_DIR,
        help="Directory to scan recursively. Default: knowledge/",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and chunk only. Do not call OpenAI or Qdrant.",
    )
    return parser.parse_args()


def print_summary(summary: IngestSummary, dry_run: bool) -> None:
    mode = "dry-run" if dry_run else "ingest"
    print(f"\n[{mode} summary]")
    print(f"Total md files: {summary.total_files}")
    print(f"Success files: {summary.success_files}")
    print(f"Failed files: {summary.failed_files}")
    print(f"Generated chunks: {summary.generated_chunks}")
    print(f"Upserted points: {summary.upserted_points}")

    if summary.failures:
        print("\n[failures]")
        for path, error in summary.failures:
            print(f"- {path}: {error}")


def main() -> int:
    args = parse_args()
    load_dotenv()

    target_dir = (PROJECT_ROOT / args.target_dir).resolve()
    parser = MarkdownParser()
    chunker = TextChunker()

    try:
        markdown_files = find_markdown_files(target_dir)
    except Exception as exc:
        print("[error]")
        print(exc)
        return 1

    summary = IngestSummary(total_files=len(markdown_files))

    embedding_service = None
    qdrant_service = None

    if not args.dry_run:
        from src.services.embedding_service import EmbeddingService
        from src.services.qdrant_service import QdrantService

        qdrant_url = os.getenv("QDRANT_URL", QDRANT_URL)
        collection_name = os.getenv("QDRANT_COLLECTION", COLLECTION_NAME)
        embedding_service = EmbeddingService()
        qdrant_service = QdrantService(url=qdrant_url, collection_name=collection_name)
        qdrant_service.ensure_collection()
        print(f"Qdrant collection ready: {collection_name}")

    for md_path in markdown_files:
        relative_path = md_path.relative_to(PROJECT_ROOT)

        try:
            parsed = parser.parse(md_path)
            chunks = chunker.split(parsed)
            summary.generated_chunks += len(chunks)

            if args.dry_run:
                print(
                    f"[dry-run] {relative_path} -> "
                    f"{len(chunks)} chunks / title: {parsed.metadata.get('title')}"
                )
            else:
                assert embedding_service is not None
                assert qdrant_service is not None

                embedded_chunks = embedding_service.embed_chunks(chunks)
                qdrant_service.upsert_chunks(embedded_chunks)
                summary.upserted_points += len(embedded_chunks)
                print(f"[upserted] {relative_path} -> {len(embedded_chunks)} points")

            summary.success_files += 1
        except Exception as exc:
            summary.failed_files += 1
            summary.failures.append((relative_path, str(exc)))

    print_summary(summary, dry_run=args.dry_run)
    return 1 if summary.failed_files else 0


if __name__ == "__main__":
    raise SystemExit(main())
