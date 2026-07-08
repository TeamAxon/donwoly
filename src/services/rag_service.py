from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from config.settings import CHAT_MODEL


class RAGService:
    def __init__(
        self,
        embedding_service,
        qdrant_service,
        llm_model: str = CHAT_MODEL,
    ):
        load_dotenv()

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key or api_key.startswith("your_"):
            raise ValueError(
                "OPENAI_API_KEY is missing. Add it to your .env file before asking RAG."
            )

        self.embedding_service = embedding_service
        self.qdrant_service = qdrant_service
        self.llm_model = os.getenv("OPENAI_CHAT_MODEL", llm_model)
        self.client = OpenAI(api_key=api_key)

    def answer(self, question: str, limit: int = 3) -> dict[str, Any]:
        query_vector = self.embedding_service.embed_text(question)
        search_results = self.qdrant_service.search(query_vector, limit=limit)

        context = self._build_context(search_results)
        prompt = self._build_prompt(question, context)

        response = self.client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 외교부 공공데이터 및 공식 출처 기준으로 답변하는 "
                        "첫달가이드 RAG 어시스턴트입니다. 제공된 context 안에서만 "
                        "답변하세요. 제공된 자료만으로 확인하기 어려운 내용은 "
                        "'제공된 자료만으로는 확인하기 어렵습니다'라고 답변하세요. "
                        "비자, 법률, 노동 관련 최종 판단을 단정하지 말고, 사용자가 "
                        "이해하기 쉬운 한국어로 설명하세요."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        answer = response.choices[0].message.content or ""

        return {
            "answer": answer,
            "sources": self._build_sources(search_results),
        }

    def _build_context(self, search_results) -> str:
        context_blocks = []

        for index, result in enumerate(search_results, start=1):
            payload = result.payload or {}
            title = payload.get("title", "제목 없음")
            source = payload.get("source", "출처 없음")
            text = payload.get("text", "")

            context_blocks.append(
                f"[문서 {index}]\n"
                f"title: {title}\n"
                f"source: {source}\n"
                f"text:\n{text}"
            )

        return "\n\n---\n\n".join(context_blocks)

    def _build_prompt(self, question: str, context: str) -> str:
        return (
            "아래 context만 근거로 사용자 질문에 답변하세요.\n\n"
            f"[context]\n{context}\n\n"
            f"[question]\n{question}\n\n"
            "답변에는 '외교부 공공데이터 및 공식 출처 기준'이라는 표현을 포함하세요."
        )

    def _build_sources(self, search_results) -> list[dict[str, Any]]:
        sources = []

        for result in search_results:
            payload = result.payload or {}
            sources.append(
                {
                    "title": payload.get("title"),
                    "source": payload.get("source"),
                    "score": result.score,
                }
            )

        return sources
