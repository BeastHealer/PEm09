"""RAG mode handler — retrieval-augmented generation."""

from __future__ import annotations

from typing import Optional

from openai import AsyncOpenAI

from services.context_store import ContextStore
from services.rag_service import RAGService
from utils.config import Settings, get_settings
from utils.logger import get_logger

logger = get_logger(__name__)

RAG_SYSTEM_PROMPT = """Ты — эксперт-ассистент по промпт-инжинирингу.
Отвечай строго на основе предоставленного контекста из базы знаний курса.
Если информации недостаточно — честно скажи об этом и предложи уточнить вопрос.
Цитируй источники в формате [источник: имя_файла].
Отвечай на русском языке, структурированно."""


class RAGHandler:
    """Answer questions using Chroma retrieval + GPT synthesis."""

    def __init__(
        self,
        context_store: ContextStore,
        rag_service: RAGService,
        settings: Optional[Settings] = None,
    ) -> None:
        self.context_store = context_store
        self.rag_service = rag_service
        self.settings = settings or get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)

    async def handle(self, user_id: str, user_message: str) -> str:
        await self.context_store.add_message(user_id, "user", user_message)

        docs = await self.rag_service.search(user_message)
        context_block = self.rag_service.format_context(docs)
        history = await self.context_store.get_history(user_id)

        # Exclude the just-added user message from history (it's in the prompt).
        prior_history = history[:-1] if history else []

        messages: list[dict[str, str]] = [
            {"role": "system", "content": RAG_SYSTEM_PROMPT},
            {
                "role": "system",
                "content": f"Контекст из базы знаний:\n\n{context_block}",
            },
            *prior_history,
            {"role": "user", "content": user_message},
        ]

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.openai_chat_model,
                messages=messages,
                temperature=0.3,
                max_tokens=1800,
            )
            answer = response.choices[0].message.content or "Не удалось сформировать ответ."
        except Exception as exc:
            logger.exception("RAG handler OpenAI error: %s", exc)
            answer = f"⚠️ Ошибка RAG-запроса: {exc}"

        await self.context_store.add_message(user_id, "assistant", answer)
        return answer

    async def answer_with_context(self, user_id: str, user_message: str) -> str:
        """Public alias used by voice handler when mode is rag."""
        return await self.handle(user_id, user_message)
