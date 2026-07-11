"""
Telegram handlers — duplicate interface for the course assistant.
Reuses the same router and session storage as the web app.
"""

from pathlib import Path

from telebot import types

from config import BotMode, VoiceType, DEFAULT_MODE, TELEGRAM_ENABLED
from services.router import route_text_request, route_voice_request, route_image_request
from services.tts import generate_voice_response, get_voice_info
from utils.logging import logger
from utils.helpers import user_sessions, save_file_async, cleanup_files, cleanup_file
from utils.prompts import WELCOME_TELEGRAM, HELP_TELEGRAM

if not TELEGRAM_ENABLED:
    raise ImportError("Telegram bot is not enabled")

from telegram_bot import telegram_bot as bot


@bot.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_sessions.set_mode(user_id, DEFAULT_MODE)
    logger.info(f"Telegram user {user_id} started")
    await bot.send_message(message.chat.id, WELCOME_TELEGRAM)


@bot.message_handler(commands=["help"])
async def cmd_help(message: types.Message):
    await bot.send_message(message.chat.id, HELP_TELEGRAM)


@bot.message_handler(commands=["reset"])
async def cmd_reset(message: types.Message):
    user_id = message.from_user.id
    user_sessions.clear_history(user_id)
    await bot.send_message(message.chat.id, "✅ История диалога очищена!")


@bot.message_handler(commands=["stats"])
async def cmd_stats(message: types.Message):
    try:
        from rag.query import get_knowledge_base_stats
        stats = get_knowledge_base_stats()
        text = (
            f"📊 **База знаний курса**\n\n"
            f"Фрагментов: {stats.get('total_documents', 0)}\n"
            f"Источники: FAQ.pdf, course.txt, RTFM.docx"
        )
        await bot.send_message(message.chat.id, text)
    except Exception as e:
        await bot.send_message(message.chat.id, f"⚠️ Ошибка: {e}")


@bot.message_handler(commands=["mode"])
async def cmd_mode(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        current = user_sessions.get_mode(user_id)
        await bot.send_message(
            message.chat.id,
            f"🔧 Текущий режим: `{current}`\n\n"
            f"Доступные: `rag`, `text`, `voice`, `vision`\n"
            f"Пример: /mode rag"
        )
        return

    new_mode = args[1].lower()
    if new_mode not in (BotMode.TEXT, BotMode.VOICE, BotMode.VISION, BotMode.RAG):
        await bot.send_message(message.chat.id, f"❌ Неизвестный режим: {new_mode}")
        return

    user_sessions.set_mode(user_id, new_mode)
    await bot.send_message(message.chat.id, f"✅ Режим: `{new_mode}`")


@bot.message_handler(commands=["voice"])
async def cmd_voice(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        current = user_sessions.get_voice(user_id)
        info = get_voice_info(current)
        await bot.send_message(
            message.chat.id,
            f"🔊 Голос: {info['name']} (`{current}`)\n"
            f"Доступные: alloy, echo, nova, fable, onyx, shimmer"
        )
        return

    voice = args[1].lower()
    valid = [VoiceType.ALLOY, VoiceType.ECHO, VoiceType.NOVA,
             VoiceType.FABLE, VoiceType.ONYX, VoiceType.SHIMMER]
    if voice not in valid:
        await bot.send_message(message.chat.id, f"❌ Неизвестный голос: {voice}")
        return

    user_sessions.set_voice(user_id, voice)
    await bot.send_message(message.chat.id, f"✅ Голос: `{voice}`")


@bot.message_handler(content_types=["photo"])
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    await bot.send_chat_action(message.chat.id, "typing")

    try:
        photo = message.photo[-1]
        caption = message.caption
        file_info = await bot.get_file(photo.file_id)
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file_info.file_path}"

        response = await route_image_request(
            user_id=user_id, image_url=file_url, caption=caption
        )
        await bot.send_message(
            message.chat.id,
            f"🔍 **Анализ изображения:**\n\n{response['text']}"
        )
    except Exception as e:
        logger.error(f"Telegram photo error: {e}")
        await bot.send_message(message.chat.id, "❌ Ошибка анализа изображения.")


@bot.message_handler(content_types=["voice"])
async def handle_voice(message: types.Message):
    user_id = message.from_user.id
    await bot.send_chat_action(message.chat.id, "typing")

    voice_path = None
    audio_path = None

    try:
        file_info = await bot.get_file(message.voice.file_id)
        voice_bytes = await bot.download_file(file_info.file_path)
        voice_path = await save_file_async(voice_bytes, "ogg")

        response = await route_voice_request(user_id, voice_path)

        await bot.send_message(
            message.chat.id,
            f"🎤 **Распознано:**\n_{response.get('transcription', '')}_"
        )
        await bot.send_message(message.chat.id, response["text"])

        audio_path = response.get("voice_path")
        if audio_path:
            with open(audio_path, "rb") as audio:
                await bot.send_voice(message.chat.id, audio)
    except Exception as e:
        logger.error(f"Telegram voice error: {e}")
        await bot.send_message(message.chat.id, "❌ Ошибка обработки голоса.")
    finally:
        cleanup_files(voice_path, audio_path)


@bot.message_handler(func=lambda m: m.content_type == "text" and not m.text.startswith("/"))
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    text = message.text
    await bot.send_chat_action(message.chat.id, "typing")

    try:
        response = await route_text_request(user_id, text)
        mode = user_sessions.get_mode(user_id)

        await bot.send_message(message.chat.id, response["text"])

        if mode == BotMode.VOICE and not response.get("has_image"):
            voice_path = await generate_voice_response(
                response["text"], voice=user_sessions.get_voice(user_id)
            )
            try:
                with open(voice_path, "rb") as audio:
                    await bot.send_voice(message.chat.id, audio)
            finally:
                cleanup_file(voice_path)

        if response.get("has_image") and response.get("image_path"):
            image_path = Path(response["image_path"])
            try:
                with open(image_path, "rb") as photo:
                    await bot.send_photo(message.chat.id, photo)
            finally:
                cleanup_file(image_path)

    except Exception as e:
        logger.error(f"Telegram text error: {e}")
        await bot.send_message(message.chat.id, "❌ Ошибка обработки сообщения.")
