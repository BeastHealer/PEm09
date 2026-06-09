"""FastAPI web interface sharing the same router as Telegram bot."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.router import IncomingMessage, MessageRouter  # noqa: E402
from utils.config import get_settings  # noqa: E402
from utils.logger import get_logger, setup_logging  # noqa: E402

logger = get_logger(__name__)
settings = get_settings()
router = MessageRouter()

app = FastAPI(
    title="Prompt Engineering Assistant",
    description="Multimodal assistant for prompt engineering coursework",
    version="1.0.0",
)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
async def startup_event() -> None:
    setup_logging(settings.log_level)
    await router.initialize()
    logger.info("Web app started on %s:%s", settings.web_host, settings.web_port)


def _resolve_user_id(session_id: Optional[str]) -> str:
    return session_id or f"web-{uuid.uuid4().hex[:12]}"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "default_mode": "text"},
    )


@app.get("/api/mode/{user_id}")
async def get_mode(user_id: str) -> JSONResponse:
    mode = await router.get_user_mode(user_id)
    return JSONResponse({"user_id": user_id, "mode": mode})


@app.post("/api/chat")
async def chat(
    message: str = Form(""),
    session_id: Optional[str] = Form(None),
    mode: Optional[str] = Form(None),
    reply_with_voice: bool = Form(False),
) -> JSONResponse:
    user_id = _resolve_user_id(session_id)

    if mode:
        await router.context_store.set_mode(user_id, mode)

    incoming = IncomingMessage(
        user_id=user_id,
        message_type="text",
        text=message,
        reply_with_voice=reply_with_voice,
    )
    response = await router.route(incoming)

    payload = {
        "user_id": user_id,
        "text": response.text,
        "has_audio": response.audio_bytes is not None,
        "metadata": response.metadata,
    }

    if response.audio_bytes:
        import base64

        payload["audio_base64"] = base64.b64encode(response.audio_bytes).decode("utf-8")

    return JSONResponse(payload)


@app.post("/api/voice")
async def voice_chat(
    audio: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    mode: Optional[str] = Form(None),
    reply_with_voice: bool = Form(True),
) -> JSONResponse:
    user_id = _resolve_user_id(session_id)

    if mode:
        await router.context_store.set_mode(user_id, mode)

    audio_bytes = await audio.read()
    incoming = IncomingMessage(
        user_id=user_id,
        message_type="voice",
        voice_bytes=audio_bytes,
        voice_filename=audio.filename or "voice.webm",
        reply_with_voice=reply_with_voice,
    )
    response = await router.route(incoming)

    payload = {
        "user_id": user_id,
        "text": response.text,
        "has_audio": response.audio_bytes is not None,
    }
    if response.audio_bytes:
        import base64

        payload["audio_base64"] = base64.b64encode(response.audio_bytes).decode("utf-8")

    return JSONResponse(payload)


@app.post("/api/image")
async def image_chat(
    image: UploadFile = File(...),
    prompt: str = Form(""),
    session_id: Optional[str] = Form(None),
) -> JSONResponse:
    user_id = _resolve_user_id(session_id)
    await router.context_store.set_mode(user_id, "image")

    image_bytes = await image.read()
    mime = image.content_type or "image/jpeg"

    incoming = IncomingMessage(
        user_id=user_id,
        message_type="image",
        image_bytes=image_bytes,
        image_mime=mime,
        text=prompt or None,
    )
    response = await router.route(incoming)

    return JSONResponse({"user_id": user_id, "text": response.text})


@app.post("/api/command")
async def run_command(
    command: str = Form(...),
    session_id: Optional[str] = Form(None),
) -> JSONResponse:
    user_id = _resolve_user_id(session_id)
    incoming = IncomingMessage(
        user_id=user_id,
        message_type="command",
        text=command,
    )
    response = await router.route(incoming)
    return JSONResponse({"user_id": user_id, "text": response.text, "metadata": response.metadata})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
