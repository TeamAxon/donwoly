"""Inspect the live Qdrant collection without modifying it."""

import os
import sys

from qdrant_client import QdrantClient


COLLECTION_NAME = "first_month_guide"
EXPECTED_CATEGORIES = {"visa", "departure", "labor", "tax", "life"}
EXPECTED_VECTOR_SIZE = 1536


def main() -> int:
    qdrant_url = os.getenv("QDRANT_URL")
    if not qdrant_url:
        print("QDRANT_URL is required", file=sys.stderr)
        return 2

    client = QdrantClient(url=qdrant_url, check_compatibility=False)
    collection = client.get_collection(COLLECTION_NAME)
    vectors = collection.config.params.vectors
    sparse_vectors = collection.config.params.sparse_vectors or {}

    if isinstance(vectors, dict):
        vector_sizes = {name: params.size for name, params in vectors.items()}
        distances = {name: str(params.distance) for name, params in vectors.items()}
    else:
        vector_sizes = {"default": vectors.size}
        distances = {"default": str(vectors.distance)}

    points = []
    offset = None
    while True:
        page, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=256,
            offset=offset,
            with_payload=["category", "text"],
            with_vectors=False,
        )
        points.extend(page)
        if offset is None:
            break
    categories = {
        point.payload.get("category")
        for point in points
        if point.payload and point.payload.get("category")
    }
    text_lengths = [
        len(point.payload.get("text", ""))
        for point in points
        if point.payload and point.payload.get("text")
    ]

    print(f"collection={COLLECTION_NAME}")
    print(f"points_count={collection.points_count}")
    print(f"vector_sizes={vector_sizes}")
    print(f"distances={distances}")
    print(f"sparse_vectors={list(sparse_vectors)}")
    print(f"categories={sorted(categories)}")
    if text_lengths:
        print(
            "text_length="
            f"min:{min(text_lengths)}, max:{max(text_lengths)}, avg:{sum(text_lengths) // len(text_lengths)}"
        )

    sizes_match = EXPECTED_VECTOR_SIZE in vector_sizes.values()
    categories_match = categories == EXPECTED_CATEGORIES
    if not sizes_match:
        print("ERROR: expected a 1536-dimensional vector", file=sys.stderr)
    if not categories_match:
        print(
            f"ERROR: expected categories {sorted(EXPECTED_CATEGORIES)}, got {sorted(categories)}",
            file=sys.stderr,
        )
    return 0 if sizes_match and categories_match else 1


if __name__ == "__main__":
    raise SystemExit(main())
