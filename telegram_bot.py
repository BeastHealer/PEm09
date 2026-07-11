"""
Telegram Bot instance (duplicate interface).
"""

from telebot.async_telebot import AsyncTeleBot

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_ENABLED
from utils.logging import logger

telegram_bot = None

if TELEGRAM_ENABLED:
    telegram_bot = AsyncTeleBot(TELEGRAM_BOT_TOKEN, parse_mode="Markdown")
    logger.info("Telegram bot instance created")
else:
    logger.info("Telegram bot disabled (TELEGRAM_BOT_TOKEN not set)")
