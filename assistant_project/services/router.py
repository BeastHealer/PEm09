"""Message routing by mode and content type."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Optional

from handlers.image_handler import ImageHandler
from handlers.rag_handler import RAGHandler
from handlers.text_handler import TextHandler
from handlers.voice_handler import VoiceHandler
from services.context_store import ContextStore
from services.rag_service import RAGService
from utils.logger import get_logger

logger = get_logger(__name__)

Mode = Literal["text", "rag", "voice", "image"]
MessageType = Literal["text", "voice", "image", "command"]


class Command(str, Enum):
    MODE = "/mode"
    RESET = "/reset"
    HELP = "/help"
    INDEX = "/index"
    STATS = "/stats"


@dataclass
class IncomingMessage:
    """Normalized message from Telegram or Web."""

    user_id: str
    message_type: MessageType
    text: Optional[str] = None
    voice_bytes: Optional[bytes] = None
    voice_filename: str = "voice.ogg"
    image_bytes: Optional[bytes] = None
    image_mime: str = "image/jpeg"
    reply_with_voice: bool = False


@dataclass
class RouterResponse:
    """Unified response for any transport layer."""

    text: str
    audio_bytes: Optional[bytes] = None
    audio_filename: str = "response.mp3"
    metadata: dict[str, Any] = field(default_factory=dict)


HELP_TEXT = """
🎓 *Мультимодальный ассистент по промпт-инжинирингу*

*Команды:*
/mode text — обычный диалог с GPT
/mode rag — ответы на основе базы знаний (RAG)
/mode voice — голосовые сообщения (Whisper + опционально TTS)
/mode image — анализ изображений (GPT-4o Vision)
/reset — очистить историю диалога
/index — переиндексировать файлы из data/
/stats — статистика RAG и контекста
/help — эта справка

*Режимы:*
• *text* — задавайте вопросы о промпт-инжиниринге
• *rag* — ответы с опорой на FAQ.pdf, course.txt, RTFM.docx
• *voice* — отправьте голосовое, получите текст или аудио-ответ
• *image* — отправьте скриншот промпта или схемы для анализа
""".strip()


class MessageRouter:
    """Dispatch incoming messages to the appropriate handler."""

    VALID_MODES = {"text", "rag", "voice", "image"}

    def __init__(
        self,
        context_store: Optional[ContextStore] = None,
        rag_service: Optional[RAGService] = None,
    ) -> None:
        self.context_store = context_store or ContextStore()
        self.rag_service = rag_service or RAGService()
        self.text_handler = TextHandler(self.context_store)
        self.rag_handler = RAGHandler(self.context_store, self.rag_service)
        self.voice_handler = VoiceHandler(self.context_store, self.rag_service)
        self.image_handler = ImageHandler(self.context_store)

    async def initialize(self) -> None:
        await self.context_store.initialize()

    async def route(self, message: IncomingMessage) -> RouterResponse:
        """Route message to handler based on type, mode, and commands."""
        await self.initialize()

        if message.text and message.text.strip().startswith("/"):
            return await self._handle_command(message)

        mode = await self.context_store.get_mode(message.user_id)
        logger.info(
            "Routing user=%s mode=%s type=%s",
            message.user_id,
            mode,
            message.message_type,
        )

        if message.message_type == "image" or mode == "image":
            if not message.image_bytes:
                return RouterResponse(
                    text="📷 Режим image: отправьте изображение для анализа."
                )
            result = await self.image_handler.handle(
                user_id=message.user_id,
                image_bytes=message.image_bytes,
                prompt=message.text,
                mime_type=message.image_mime,
            )
            return RouterResponse(text=result)

        if message.message_type == "voice" or mode == "voice":
            if message.voice_bytes:
                text, audio = await self.voice_handler.handle_voice_input(
                    user_id=message.user_id,
                    audio_bytes=message.voice_bytes,
                    filename=message.voice_filename,
                    reply_with_voice=message.reply_with_voice or mode == "voice",
                    use_rag=mode == "rag",
                )
                return RouterResponse(
                    text=text,
                    audio_bytes=audio,
                    metadata={"transcribed": True},
                )
            if message.text:
                text, audio = await self.voice_handler.handle_text_to_speech(
                    user_id=message.user_id,
                    text=message.text,
                    use_rag=mode == "rag",
                )
                return RouterResponse(text=text, audio_bytes=audio)

        if mode == "rag":
            if not message.text:
                return RouterResponse(text="💬 Режим RAG: задайте текстовый вопрос.")
            answer = await self.rag_handler.handle(message.user_id, message.text)
            return RouterResponse(text=answer)

        if not message.text:
            return RouterResponse(text="💬 Отправьте текстовое сообщение.")

        answer = await self.text_handler.handle(message.user_id, message.text)
        return RouterResponse(text=answer)

    async def _handle_command(self, message: IncomingMessage) -> RouterResponse:
        text = (message.text or "").strip()
        parts = text.split(maxsplit=2)
        command = parts[0].lower()
        user_id = message.user_id

        if command == Command.HELP.value:
            return RouterResponse(text=HELP_TEXT)

        if command == Command.RESET.value:
            await self.context_store.reset(user_id)
            return RouterResponse(text="🔄 История диалога очищена.")

        if command == Command.MODE.value:
            if len(parts) < 2:
                current = await self.context_store.get_mode(user_id)
                return RouterResponse(
                    text=f"Текущий режим: *{current}*\n"
                    f"Использование: /mode [text|rag|voice|image]"
                )
            new_mode = parts[1].lower()
            if new_mode not in self.VALID_MODES:
                return RouterResponse(
                    text="❌ Неизвестный режим. Доступны: text, rag, voice, image"
                )
            await self.context_store.set_mode(user_id, new_mode)
            hints = {
                "text": "Задавайте вопросы в свободной форме.",
                "rag": "Вопросы будут обрабатываться на основе базы знаний.",
                "voice": "Отправляйте голосовые сообщения.",
                "image": "Отправляйте изображения для анализа.",
            }
            return RouterResponse(
                text=f"✅ Режим переключён на *{new_mode}*\n{hints[new_mode]}"
            )

        if command == Command.INDEX.value:
            result = await self.rag_service.index_documents()
            if result["success"]:
                return RouterResponse(
                    text=(
                        f"✅ Индексация завершена\n"
                        f"📄 Документов: {result['documents_indexed']}\n"
                        f"🧩 Чанков: {result['chunks_created']}"
                    ),
                    metadata=result,
                )
            return RouterResponse(text=f"❌ {result['message']}", metadata=result)

        if command == Command.STATS.value:
            rag_stats = await self.rag_service.get_stats()
            ctx_stats = await self.context_store.get_stats()
            current_mode = await self.context_store.get_mode(user_id)
            stats_text = (
                "📊 *Статистика RAG*\n"
                f"• Коллекция: `{rag_stats['collection_name']}`\n"
                f"• Документов: {rag_stats['documents_in_metadata']}\n"
                f"• Чанков (metadata): {rag_stats['total_chunks_metadata']}\n"
                f"• Записей в Chroma: {rag_stats['collection_count']}\n"
                f"• Размер Chroma: {rag_stats['chroma_size_mb']} MB\n"
                f"• Последняя индексация: {rag_stats['last_indexed_at'] or '—'}\n\n"
                f"💾 *Контекст SQLite*\n"
                f"• Пользователей: {ctx_stats['users_with_messages']}\n"
                f"• Сообщений: {ctx_stats['total_messages']}\n\n"
                f"🎯 Ваш режим: *{current_mode}*"
            )
            return RouterResponse(text=stats_text, metadata={**rag_stats, **ctx_stats})

        return RouterResponse(
            text="❓ Неизвестная команда. Используйте /help для справки."
        )

    async def get_user_mode(self, user_id: str) -> str:
        await self.initialize()
        return await self.context_store.get_mode(user_id)
