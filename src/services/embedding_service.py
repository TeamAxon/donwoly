from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from config.settings import EMBEDDING_MODEL, VECTOR_SIZE
from src.chunkers.text_chunker import Chunk


@dataclass(frozen=True)
class EmbeddedChunk:
    id: str
    text: str
    metadata: dict[str, Any]
    vector: list[float]


class EmbeddingService:
    """Create OpenAI embedding vectors from chunk text.

    Chunk.text is the only text sent to the embedding model.
    Chunk.metadata is kept as future Qdrant payload and is not embedded.
    """

    def __init__(self, model: str = EMBEDDING_MODEL):
        load_dotenv()

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key or api_key.startswith("your_"):
            raise ValueError(
                "OPENAI_API_KEY is missing. Add it to your .env file before embedding."
            )

        self.model = os.getenv("OPENAI_EMBEDDING_MODEL", model)
        self.client = OpenAI(api_key=api_key)

    def embed_text(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("Cannot embed empty text.")

        response = self.client.embeddings.create(
            model=self.model,
            input=text,
        )

        vector = response.data[0].embedding
        if len(vector) != VECTOR_SIZE:
            raise ValueError(
                f"Embedding dimension mismatch: expected {VECTOR_SIZE}, "
                f"got {len(vector)}."
            )

        return vector

    def embed_chunks(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
        embedded_chunks: list[EmbeddedChunk] = []

        for chunk in chunks:
            vector = self.embed_text(chunk.text)
            embedded_chunks.append(
                EmbeddedChunk(
                    id=chunk.id,
                    text=chunk.text,
                    metadata=dict(chunk.metadata),
                    vector=vector,
                )
            )

        return embedded_chunks
