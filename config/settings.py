"""Project-wide settings for the RAG data pipeline."""

COLLECTION_NAME = "first_month_guide"
EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"
VECTOR_SIZE = 1536
DISTANCE_METRIC = "cosine"
QDRANT_URL = "http://localhost:6333"

KNOWLEDGE_DIR = "knowledge"
