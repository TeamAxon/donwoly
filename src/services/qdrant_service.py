from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from config.settings import DISTANCE_METRIC, VECTOR_SIZE
from src.services.embedding_service import EmbeddedChunk


class QdrantService:
    def __init__(self, url: str, collection_name: str):
        self.url = url
        self.collection_name = collection_name
        self.client = QdrantClient(url=url)

    def ensure_collection(self):
        collection_names = [
            collection.name for collection in self.client.get_collections().collections
        ]

        if self.collection_name in collection_names:
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=self._distance(),
            ),
        )

    def upsert_chunks(self, embedded_chunks: list[EmbeddedChunk]):
        points = []

        for chunk in embedded_chunks:
            payload: dict[str, Any] = dict(chunk.metadata)
            payload["text"] = chunk.text
            payload["embedded_chunk_id"] = chunk.id

            point_id = payload.get("qdrant_point_id")
            if not point_id:
                raise ValueError(f"Missing qdrant_point_id for chunk: {chunk.id}")

            points.append(
                PointStruct(
                    id=point_id,
                    vector=chunk.vector,
                    payload=payload,
                )
            )

        if not points:
            return

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

    def search(self, query_vector: list[float], limit: int = 5):
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True,
        )
        return response.points

    def _distance(self) -> Distance:
        metric = DISTANCE_METRIC.lower()

        if metric == "cosine":
            return Distance.COSINE
        if metric == "dot":
            return Distance.DOT
        if metric in {"euclid", "euclidean"}:
            return Distance.EUCLID

        raise ValueError(f"Unsupported Qdrant distance metric: {DISTANCE_METRIC}")
