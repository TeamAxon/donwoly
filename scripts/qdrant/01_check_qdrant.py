import sys
from pathlib import Path

from qdrant_client import QdrantClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from config.qdrant_config import COLLECTION_NAME, QDRANT_HOST, QDRANT_PORT


def main():
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    collections = client.get_collections().collections
    collection_names = [collection.name for collection in collections]

    print("Qdrant connection: OK")
    print("Collections:", collection_names)

    if COLLECTION_NAME in collection_names:
        print(f"Collection '{COLLECTION_NAME}' exists.")
    else:
        print(f"Collection '{COLLECTION_NAME}' does not exist yet.")


if __name__ == "__main__":
    main()
