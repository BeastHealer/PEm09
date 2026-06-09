"""Voice mode handler — Whisper STT and OpenAI TTS."""

from __future__ import annotations

import io
from typing import Optional

from openai import AsyncOpenAI

from handlers.rag_handler import RAGHandler
from handlers.text_handler import TextHandler
from services.context_store import ContextStore
from services.rag_service import RAGService
from utils.config import Settings, get_settings
from utils.logger import get_logger

logger = get_logger(__name__)


class VoiceHandler:
    """Speech-to-text and text-to-speech pipeline."""

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
        self.text_handler = TextHandler(context_store, self.settings)
        self.rag_handler = RAGHandler(context_store, rag_service, self.settings)

    async def transcribe(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        """Convert speech to text via Whisper."""
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename

        try:
            transcript = await self.client.audio.transcriptions.create(
                model=self.settings.openai_whisper_model,
                file=audio_file,
                language="ru",
            )
            return transcript.text.strip()
        except Exception as exc:
            logger.exception("Whisper transcription failed: %s", exc)
            raise RuntimeError(f"Ошибка распознавания речи: {exc}") from exc

    async def synthesize(self, text: str) -> bytes:
        """Convert text to speech via OpenAI TTS."""
        try:
            response = await self.client.audio.speech.create(
                model=self.settings.openai_tts_model,
                voice=self.settings.openai_tts_voice,
                input=text[:4096],
            )
            return response.content
        except Exception as exc:
            logger.exception("TTS synthesis failed: %s", exc)
            raise RuntimeError(f"Ошибка синтеза речи: {exc}") from exc

    async def _generate_answer(
        self,
        user_id: str,
        text: str,
        *,
        use_rag: bool,
    ) -> str:
        if use_rag:
            return await self.rag_handler.handle(user_id, text)
        return await self.text_handler.handle(user_id, text)

    async def handle_voice_input(
        self,
        user_id: str,
        audio_bytes: bytes,
        filename: str = "voice.ogg",
        *,
        reply_with_voice: bool = False,
        use_rag: bool = False,
    ) -> tuple[str, Optional[bytes]]:
        """
        Process voice message: STT -> LLM -> optional TTS.

        Returns (text_response, optional_audio_bytes).
        """
        try:
            transcribed = await self.transcribe(audio_bytes, filename)
        except RuntimeError as exc:
            return str(exc), None

        if not transcribed:
            return "🎤 Не удалось распознать речь. Попробуйте ещё раз.", None

        header = f"🎤 *Распознано:* {transcribed}\n\n"
        answer = await self._generate_answer(user_id, transcribed, use_rag=use_rag)
        full_text = header + answer

        audio_out: Optional[bytes] = None
        if reply_with_voice:
            try:
                audio_out = await self.synthesize(answer)
            except RuntimeError as exc:
                full_text += f"\n\n⚠️ {exc}"

        return full_text, audio_out

    async def handle_text_to_speech(
        self,
        user_id: str,
        text: str,
        *,
        use_rag: bool = False,
    ) -> tuple[str, Optional[bytes]]:
        """Generate LLM answer and optionally return TTS audio."""
        answer = await self._generate_answer(user_id, text, use_rag=use_rag)
        audio_out: Optional[bytes] = None
        try:
            audio_out = await self.synthesize(answer)
        except RuntimeError as exc:
            answer += f"\n\n⚠️ {exc}"
        return answer, audio_out
