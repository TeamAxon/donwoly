"""Run read-only live RAG checks for representative Korean questions."""

import asyncio
import logging
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chat.answer_generation import generate_answer  # noqa: E402
from chat.query_understanding import interpret_query  # noqa: E402
from rag.qdrant_search import QdrantSearchError, search_chunks  # noqa: E402


QUESTIONS = [
    "세컨 비자 받으려면 뭐가 필요해?",
    "월급 명세서 언제까지 줘야 돼?",
    "응급실 가면 돈 얼마나 나와?",
]
PROFILE = {"age": 25, "region": "SYDNEY", "industry": "HOSPITALITY"}


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    for question in QUESTIONS:
        interpretation = await interpret_query(question, PROFILE)
        category = interpretation["category"]
        search_query_en = interpretation["search_query_en"]
        print(f"\nquestion_ko={question}")
        print(f"category={category}")
        print(f"search_query_en={search_query_en}")

        try:
            chunks = search_chunks(search_query_en, category=category, top_k=5)
        except QdrantSearchError as exc:
            print(f"search_error={exc}")
            continue
        for index, chunk in enumerate(chunks, start=1):
            payload = chunk.get("payload", {})
            print(
                f"result_{index}=score:{float(chunk.get('score', 0)):.4f} "
                f"category:{payload.get('category')} title:{payload.get('title')}"
            )

        generated = await generate_answer(question, chunks, PROFILE, category)
        print(
            f"answer_validation=grounded:{generated['grounded']} "
            f"confidence:{generated['confidence']}"
        )
        print(f"answer_ko={generated['answer']}")


if __name__ == "__main__":
    asyncio.run(main())
