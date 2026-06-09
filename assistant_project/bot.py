"""Telegram bot entry point for the prompt engineering assistant."""

from __future__ import annotations

import io
import sys
from pathlib import Path

# Ensure project root is on sys.path when launched as script.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from services.router import IncomingMessage, MessageRouter
from utils.config import get_settings
from utils.logger import get_logger, setup_logging

logger = get_logger(__name__)
router = MessageRouter()


async def post_init(_application: Application) -> None:
    await router.initialize()
    logger.info("Telegram bot initialized")


def _user_id(update: Update) -> str:
    user = update.effective_user
    return str(user.id if user else "anonymous")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _route_text(update, "/help")


async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = " ".join(context.args) if context.args else ""
    command = f"/mode {args}".strip()
    await _route_text(update, command)


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _route_text(update, "/reset")


async def cmd_index(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _route_text(update, "/index")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _route_text(update, "/stats")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    await _route_text(update, update.message.text)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.voice:
        return

    await update.message.chat.send_action("typing")
    voice = update.message.voice
    tg_file = await context.bot.get_file(voice.file_id)
    audio_bytes = bytes(await tg_file.download_as_bytearray())

    message = IncomingMessage(
        user_id=_user_id(update),
        message_type="voice",
        voice_bytes=audio_bytes,
        voice_filename="voice.ogg",
        reply_with_voice=True,
    )
    response = await router.route(message)
    await _send_response(update, response)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.photo:
        return

    await update.message.chat.send_action("typing")
    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    image_bytes = bytes(await tg_file.download_as_bytearray())
    caption = update.message.caption

    message = IncomingMessage(
        user_id=_user_id(update),
        message_type="image",
        image_bytes=image_bytes,
        image_mime="image/jpeg",
        text=caption,
    )
    response = await router.route(message)
    await _send_response(update, response)


async def _route_text(update: Update, text: str) -> None:
    if not update.message:
        return

    await update.message.chat.send_action("typing")
    message = IncomingMessage(
        user_id=_user_id(update),
        message_type="text",
        text=text,
    )
    response = await router.route(message)
    await _send_response(update, response)


async def _send_response(update: Update, response) -> None:
    if not update.message:
        return

    await update.message.reply_text(
        response.text,
        parse_mode=ParseMode.MARKDOWN,
    )

    if response.audio_bytes:
        audio_io = io.BytesIO(response.audio_bytes)
        audio_io.name = response.audio_filename
        await update.message.reply_voice(voice=audio_io)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Telegram handler error: %s", context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ Произошла внутренняя ошибка. Попробуйте позже."
        )


def build_application() -> Application:
    settings = get_settings()
    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("index", cmd_index))
    app.add_handler(CommandHandler("stats", cmd_stats))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    app.add_error_handler(error_handler)
    return app


def main() -> None:
    setup_logging(get_settings().log_level)
    logger.info("Starting Telegram bot...")
    app = build_application()
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
