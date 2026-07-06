import sys
from pathlib import Path

from qdrant_client.http.exceptions import ResponseHandlingException
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from config.qdrant_config import (  # noqa: E402
    COLLECTION_NAME,
    DISTANCE_METRIC,
    QDRANT_HOST,
    QDRANT_PORT,
    VECTOR_SIZE,
)


def resolve_distance(metric_name: str) -> Distance:
    normalized = metric_name.strip().lower()

    if normalized == "cosine":
        return Distance.COSINE
    if normalized == "dot":
        return Distance.DOT
    if normalized == "euclid":
        return Distance.EUCLID

    raise ValueError(f"Unsupported distance metric: {metric_name}")


def main():
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

    try:
        collection_names = [
            collection.name for collection in client.get_collections().collections
        ]
    except ResponseHandlingException as exc:
        print("Qdrant connection failed.")
        print(f"Target: http://{QDRANT_HOST}:{QDRANT_PORT}")
        print("Make sure Docker is running and start Qdrant with:")
        print("  docker compose up --build")
        print(f"Original error: {exc}")
        return

    if COLLECTION_NAME in collection_names:
        print(f"Collection '{COLLECTION_NAME}' already exists.")
        info = client.get_collection(COLLECTION_NAME)
        print("Current collection info:")
        print(info)
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=resolve_distance(DISTANCE_METRIC),
        ),
    )

    print(f"Collection '{COLLECTION_NAME}' created.")
    print(f"Vector size: {VECTOR_SIZE}")
    print(f"Distance metric: {DISTANCE_METRIC}")


if __name__ == "__main__":
    main()
