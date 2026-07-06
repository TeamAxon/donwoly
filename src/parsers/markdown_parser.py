from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REQUIRED_METADATA_FIELDS = {
    "country",
    "country_code",
    "target_user",
    "category",
    "title",
    "chunk_id",
    "source",
    "language",
    "last_updated",
}

ALLOWED_CATEGORIES = {
    "visa",
    "departure",
    "labor_law",
    "tax",
    "life",
}


@dataclass(frozen=True)
class ParsedMarkdown:
    """A parsed knowledge document.

    metadata becomes the Qdrant payload later.
    content becomes the embedding target text later.
    source_path lets us trace a Qdrant point back to the original file.
    """

    metadata: dict[str, Any]
    content: str
    source_path: str


class MarkdownParser:
    """Parse Markdown knowledge files with YAML Front Matter.

    This parser is intentionally separated from OpenAI and Qdrant code.
    The RAG data pipeline should first prove that source documents are
    well-formed before creating embeddings or writing to a vector database.
    """

    def parse(self, file_path: str | Path) -> ParsedMarkdown:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Markdown file not found: {path}")
        if path.suffix.lower() != ".md":
            raise ValueError(f"Expected a .md file, got: {path}")

        raw_text = path.read_text(encoding="utf-8")
        metadata, content = self._split_frontmatter(raw_text, path)
        self._validate_metadata(metadata, path)

        return ParsedMarkdown(
            metadata=metadata,
            content=content.strip(),
            source_path=str(path),
        )

    def _split_frontmatter(
        self,
        raw_text: str,
        path: Path,
    ) -> tuple[dict[str, Any], str]:
        """Split YAML Front Matter and body content.

        Front Matter is the future Qdrant payload.
        The body content is the future embedding text.
        """

        if not raw_text.startswith("---\n"):
            raise ValueError(
                f"{path}: YAML Front Matter must start with '---' on the first line."
            )

        parts = raw_text.split("---", 2)
        if len(parts) < 3:
            raise ValueError(f"{path}: YAML Front Matter closing '---' is missing.")

        frontmatter_text = parts[1].strip()
        content = parts[2].strip()

        try:
            metadata = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as exc:
            raise ValueError(f"{path}: invalid YAML Front Matter: {exc}") from exc

        if not isinstance(metadata, dict):
            raise ValueError(f"{path}: YAML Front Matter must be a key-value mapping.")

        if not content:
            raise ValueError(f"{path}: Markdown body content is empty.")

        return metadata, content

    def _validate_metadata(self, metadata: dict[str, Any], path: Path) -> None:
        """Validate metadata before it becomes Qdrant payload.

        This prevents bad documents from silently entering the RAG index.
        With hundreds of Markdown files, early validation makes debugging much
        easier than discovering bad payloads after Qdrant upsert.
        """

        missing_fields = sorted(REQUIRED_METADATA_FIELDS - metadata.keys())
        if missing_fields:
            missing = ", ".join(missing_fields)
            raise ValueError(f"{path}: missing required Front Matter fields: {missing}")

        category = metadata.get("category")
        if category not in ALLOWED_CATEGORIES:
            allowed = ", ".join(sorted(ALLOWED_CATEGORIES))
            raise ValueError(
                f"{path}: invalid category '{category}'. "
                f"Allowed categories: {allowed}"
            )
