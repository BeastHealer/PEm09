"""
Configuration module for the Personal Assistant Web App.
All AI API requests go through ProxyAPI (https://proxyapi.ru/docs/overview).
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

# Flask Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"

# ProxyAPI Configuration
# Docs: https://proxyapi.ru/docs/overview
# OpenAI-compatible endpoint: https://api.proxyapi.ru/openai/v1
PROXYAPI_KEY = os.getenv("PROXYAPI_KEY") or os.getenv("OPENAI_API_KEY")
if not PROXYAPI_KEY:
    raise ValueError(
        "PROXYAPI_KEY is not set in .env file. "
        "Get your API key at https://proxyapi.ru"
    )

PROXYAPI_BASE_URL = os.getenv("PROXYAPI_BASE_URL", "https://api.proxyapi.ru").rstrip("/")
PROXYAPI_OPENAI_URL = f"{PROXYAPI_BASE_URL}/openai/v1"

# Sync environment for LangChain and OpenAI SDK auto-detection
os.environ.setdefault("OPENAI_API_KEY", PROXYAPI_KEY)
os.environ.setdefault("OPENAI_API_BASE", PROXYAPI_OPENAI_URL)

# Backward-compatible aliases used across the codebase
OPENAI_API_KEY = PROXYAPI_KEY
OPENAI_BASE_URL = PROXYAPI_OPENAI_URL

# Bot Modes
class BotMode:
    TEXT = "text"
    VOICE = "voice"
    VISION = "vision"
    RAG = "rag"

DEFAULT_MODE = os.getenv("BOT_MODE", BotMode.RAG)

# Telegram Bot (дублирующий интерфейс, опционально)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ENABLED = (
    os.getenv("TELEGRAM_ENABLED", "true").lower() == "true"
    and bool(TELEGRAM_BOT_TOKEN)
)

# Course knowledge base files
KNOWLEDGE_BASE_FILES = ["FAQ.pdf", "course.txt", "RTFM.docx"]
SUPPORTED_DOC_EXTENSIONS = [".pdf", ".txt", ".md", ".docx"]

# Voice Configuration
class VoiceType:
    ALLOY = "alloy"
    ECHO = "echo"
    NOVA = "nova"
    FABLE = "fable"
    ONYX = "onyx"
    SHIMMER = "shimmer"

DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", VoiceType.ALLOY)

# OpenAI Models (via ProxyAPI)
GPT_MODEL = "gpt-4o"
GPT_MINI_MODEL = "gpt-4o-mini"
WHISPER_MODEL = "whisper-1"
TTS_MODEL = "tts-1"
VISION_MODEL = "gpt-4o"
DALLE_MODEL = "dall-e-3"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# DALL-E Configuration
DALLE_DEFAULT_SIZE = "1024x1024"
DALLE_DEFAULT_QUALITY = "standard"
DALLE_DEFAULT_STYLE = "vivid"

# Data paths
DATA_DIR = BASE_DIR / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"
UPLOADS_DIR = DATA_DIR / "uploads"
EMBEDDINGS_DB = DATA_DIR / "embeddings.db"

DATA_DIR.mkdir(exist_ok=True)
DOCUMENTS_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = BASE_DIR / "bot.log"

# RAG Configuration
RAG_CHUNK_SIZE = 1000
RAG_CHUNK_OVERLAP = 200
RAG_TOP_K = 3

# OpenAI Settings
TEMPERATURE = 0.7
MAX_TOKENS = 1500

# User session settings
MAX_HISTORY_LENGTH = 10

# Upload limits
MAX_UPLOAD_SIZE_MB = 20

# Production safety
if not FLASK_DEBUG and SECRET_KEY == "dev-secret-change-in-production":
    import warnings
    warnings.warn(
        "SECRET_KEY is not set for production. "
        "Generate one: python -c \"import secrets; print(secrets.token_hex(32))\"",
        stacklevel=2,
    )


def proxyapi_auth_headers() -> dict:
    """Return Authorization headers for direct HTTP requests to ProxyAPI."""
    return {
        "Authorization": f"Bearer {PROXYAPI_KEY}",
        "Content-Type": "application/json",
    }
