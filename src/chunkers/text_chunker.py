from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from src.parsers.markdown_parser import ParsedMarkdown


@dataclass(frozen=True)
class Chunk:
    """A Qdrant-ready text unit.

    text becomes the embedding target later.
    metadata becomes the Qdrant payload later.
    """

    id: str
    text: str
    metadata: dict[str, Any]


class TextChunker:
    """Split a parsed Markdown document into searchable chunks."""

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0.")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative.")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size.")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, parsed_markdown: ParsedMarkdown) -> list[Chunk]:
        raw_chunks = self._split_text(parsed_markdown.content)
        chunk_count = len(raw_chunks)
        original_chunk_id = parsed_markdown.metadata["chunk_id"]

        chunks: list[Chunk] = []
        for index, text in enumerate(raw_chunks):
            chunk_id = f"{original_chunk_id}_{index}"
            qdrant_point_id = str(uuid5(NAMESPACE_URL, chunk_id))

            metadata = dict(parsed_markdown.metadata)
            metadata.update(
                {
                    "chunk_index": index,
                    "chunk_count": chunk_count,
                    "source_path": parsed_markdown.source_path,
                    "original_chunk_id": original_chunk_id,
                    "qdrant_point_id": qdrant_point_id,
                }
            )

            chunks.append(
                Chunk(
                    id=chunk_id,
                    text=text,
                    metadata=metadata,
                )
            )

        return chunks

    def _split_text(self, text: str) -> list[str]:
        paragraphs = [paragraph.strip() for paragraph in text.split("\n\n")]
        paragraphs = [paragraph for paragraph in paragraphs if paragraph]

        chunks: list[str] = []
        current = ""

        for paragraph in paragraphs:
            if len(paragraph) > self.chunk_size:
                if current:
                    chunks.append(current.strip())
                    current = ""
                chunks.extend(self._split_long_paragraph(paragraph))
                continue

            candidate = paragraph if not current else f"{current}\n\n{paragraph}"

            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                chunks.append(current.strip())
                current = self._with_overlap(chunks[-1], paragraph)

        if current:
            chunks.append(current.strip())

        return chunks

    def _split_long_paragraph(self, paragraph: str) -> list[str]:
        chunks: list[str] = []
        start = 0

        while start < len(paragraph):
            end = start + self.chunk_size
            chunks.append(paragraph[start:end].strip())

            if end >= len(paragraph):
                break

            start = max(end - self.chunk_overlap, start + 1)

        return chunks

    def _with_overlap(self, previous_chunk: str, next_paragraph: str) -> str:
        if self.chunk_overlap == 0:
            return next_paragraph

        overlap_text = previous_chunk[-self.chunk_overlap :].strip()
        if not overlap_text:
            return next_paragraph

        return f"{overlap_text}\n\n{next_paragraph}"
