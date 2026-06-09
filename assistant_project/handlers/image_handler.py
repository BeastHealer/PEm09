"""Image mode handler — GPT-4o Vision analysis."""

from __future__ import annotations

import base64
from typing import Optional

from openai import AsyncOpenAI

from services.context_store import ContextStore
from utils.config import Settings, get_settings
from utils.logger import get_logger

logger = get_logger(__name__)

VISION_SYSTEM_PROMPT = """Ты — эксперт по промпт-инжинирингу и визуальному анализу.
Анализируй изображения: скриншоты промптов, диаграммы, слайды, код.
Давай конструктивную обратную связь по качеству промптов и предложения по улучшению.
Отвечай на русском языке."""


class ImageHandler:
    """Analyze images with GPT-4o Vision."""

    def __init__(
        self,
        context_store: ContextStore,
        settings: Optional[Settings] = None,
    ) -> None:
        self.context_store = context_store
        self.settings = settings or get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)

    async def handle(
        self,
        user_id: str,
        image_bytes: bytes,
        prompt: Optional[str] = None,
        mime_type: str = "image/jpeg",
    ) -> str:
        user_prompt = prompt or (
            "Проанализируй это изображение в контексте промпт-инжиниринга. "
            "Опиши содержимое и дай рекомендации."
        )

        await self.context_store.add_message(
            user_id,
            "user",
            f"[Изображение] {user_prompt}",
        )

        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64_image}"

        messages = [
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": data_url, "detail": "auto"}},
                ],
            },
        ]

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.openai_vision_model,
                messages=messages,
                max_tokens=1500,
            )
            answer = response.choices[0].message.content or "Не удалось проанализировать изображение."
        except Exception as exc:
            logger.exception("Vision handler error: %s", exc)
            answer = f"⚠️ Ошибка анализа изображения: {exc}"

        await self.context_store.add_message(user_id, "assistant", answer)
        return answer
