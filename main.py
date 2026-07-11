"""
Main Entry Point.
Starts Flask web app (primary) and Telegram bot in background (optional).
"""

import asyncio
import sys
import threading

from config import (
    FLASK_HOST,
    FLASK_PORT,
    FLASK_DEBUG,
    TELEGRAM_ENABLED,
    DOCUMENTS_DIR,
    SUPPORTED_DOC_EXTENSIONS,
)
from utils.logging import logger


def init_rag():
    """Initialize RAG index with course knowledge base."""
    try:
        from rag.index import vector_index

        docs = [
            d for d in DOCUMENTS_DIR.glob("*")
            if d.is_file() and d.suffix.lower() in SUPPORTED_DOC_EXTENSIONS
        ]

        if docs:
            logger.info(f"Found {len(docs)} course documents, indexing...")
            count = vector_index.index_documents_directory(force_reindex=False)
            logger.info(f"Indexed {count} document chunks")
        else:
            logger.warning(
                "No documents in data/documents/. "
                "Expected: FAQ.pdf, course.txt, RTFM.docx"
            )

    except Exception as e:
        logger.warning(f"Could not initialize RAG index: {e}")


def run_web():
    """Run Flask web server (blocking)."""
    from bot import app
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG, use_reloader=False)


async def _run_telegram_async():
    """Start Telegram polling with connection check."""
    from telegram_bot import telegram_bot
    import handlers.telegram_handlers  # noqa: F401 — registers handlers

    try:
        bot_info = await asyncio.wait_for(telegram_bot.get_me(), timeout=20)
        logger.info(f"Telegram bot connected: @{bot_info.username}")
        await telegram_bot.infinity_polling(timeout=10, skip_pending=True)
    except asyncio.TimeoutError:
        logger.warning(
            "Telegram: таймаут подключения к api.telegram.org. "
            "Веб-интерфейс продолжает работать. "
            "Проверьте VPN/сеть или установите TELEGRAM_ENABLED=false в .env"
        )
    except Exception as e:
        logger.warning(
            f"Telegram bot недоступен: {e}. "
            "Веб-интерфейс продолжает работать."
        )
    finally:
        try:
            await telegram_bot.close_session()
        except Exception:
            pass


def run_telegram_background():
    """Run Telegram bot in a background daemon thread."""
    try:
        asyncio.run(_run_telegram_async())
    except Exception as e:
        logger.warning(f"Telegram thread stopped: {e}")


def main():
    """Run web app; Telegram starts in background if enabled."""
    try:
        logger.info("=" * 60)
        logger.info("Prompt Engineering Assistant — Starting")
        logger.info("=" * 60)

        from config import PROXYAPI_OPENAI_URL
        logger.info(f"AI API: {PROXYAPI_OPENAI_URL}")

        init_rag()

        if TELEGRAM_ENABLED:
            tg_thread = threading.Thread(
                target=run_telegram_background,
                name="telegram-bot",
                daemon=True,
            )
            tg_thread.start()
            logger.info("Telegram bot: starting in background...")
        else:
            logger.info(
                "Telegram bot: disabled "
                "(set TELEGRAM_BOT_TOKEN and TELEGRAM_ENABLED=true to enable)"
            )

        logger.info(f"Web UI: http://{FLASK_HOST}:{FLASK_PORT}")
        run_web()

    except KeyboardInterrupt:
        logger.info("Stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
