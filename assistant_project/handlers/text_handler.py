"""Text mode handler — direct GPT chat with conversation history."""

from __future__ import annotations

from typing import Optional

from openai import AsyncOpenAI

from services.context_store import ContextStore
from utils.config import Settings, get_settings
from utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """Ты — персональный ассистент по обучению промпт-инжинирингу.
Помогай студентам понимать:
- структуру эффективных промптов (роль, контекст, инструкции, формат вывода)
- техники: zero-shot, few-shot, chain-of-thought, role prompting
- итеративное улучшение промптов и оценку качества ответов
- работу с мультимодальными моделями

Отвечай на русском языке, структурированно и с практическими примерами.
Если вопрос выходит за рамки промпт-инжиниринга — вежливо верни разговор к теме."""


class TextHandler:
    """Handle plain text conversations via OpenAI Chat Completions."""

    def __init__(
        self,
        context_store: ContextStore,
        settings: Optional[Settings] = None,
    ) -> None:
        self.context_store = context_store
        self.settings = settings or get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)

    async def handle(self, user_id: str, user_message: str) -> str:
        await self.context_store.add_message(user_id, "user", user_message)

        history = await self.context_store.get_history(user_id)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.openai_chat_model,
                messages=messages,
                temperature=0.7,
                max_tokens=1500,
            )
            answer = response.choices[0].message.content or "Пустой ответ от модели."
        except Exception as exc:
            logger.exception("Text handler OpenAI error: %s", exc)
            answer = f"⚠️ Ошибка при обращении к OpenAI: {exc}"

        await self.context_store.add_message(user_id, "assistant", answer)
        return answer
