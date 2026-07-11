"""
Flask Web Routes.
REST API and page handlers for the web interface.
"""

import uuid
from pathlib import Path

from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    session,
    send_file,
    abort,
)
from werkzeug.utils import secure_filename

from config import (
    BotMode,
    VoiceType,
    DOCUMENTS_DIR,
    UPLOADS_DIR,
    DEFAULT_MODE,
    DEFAULT_VOICE,
    SUPPORTED_DOC_EXTENSIONS,
)
from utils.prompts import WELCOME_WEB
from services.router import (
    route_text_request,
    route_voice_request,
    route_image_request,
    route_image_generation_request,
)
from services.tts import generate_voice_response, get_voice_info
from rag.loader import document_loader
from rag.index import vector_index
from utils.logging import logger
from utils.helpers import user_sessions, cleanup_file, cleanup_files
from utils.async_runner import run_async

bp = Blueprint("main", __name__)

ALLOWED_DOC_EXTENSIONS = set(SUPPORTED_DOC_EXTENSIONS)
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_AUDIO_EXTENSIONS = {".ogg", ".wav", ".webm", ".mp3", ".m4a"}


def get_user_id() -> int:
    """Get or create a session-scoped user ID."""
    if "user_id" not in session:
        session["user_id"] = abs(hash(uuid.uuid4().hex)) % (10**9)
    return session["user_id"]


def _save_upload(file_storage, directory: Path, prefix: str = "") -> Path:
    """Save uploaded file and return path."""
    filename = secure_filename(file_storage.filename or "upload")
    filepath = directory / f"{prefix}{uuid.uuid4().hex}_{filename}"
    file_storage.save(filepath)
    return filepath


def _media_url(filepath: Path) -> str:
    """Build URL for serving a media file."""
    return f"/api/media/{filepath.name}"


@bp.route("/api/health", methods=["GET"])
def health_check():
    """Health check for deployment monitoring."""
    return jsonify({"status": "ok", "service": "prompt-engineering-assistant"})


@bp.route("/")
def index():
    """Main chat page."""
    user_id = get_user_id()
    user_sessions.set_mode(user_id, user_sessions.get_mode(user_id) or DEFAULT_MODE)
    return render_template(
        "index.html",
        modes=BotMode,
        voices=VoiceType,
        current_mode=user_sessions.get_mode(user_id),
        current_voice=user_sessions.get_voice(user_id),
        welcome_message=WELCOME_WEB,
    )


@bp.route("/api/settings", methods=["GET"])
def get_settings():
    """Return current user settings."""
    user_id = get_user_id()
    return jsonify({
        "mode": user_sessions.get_mode(user_id),
        "voice": user_sessions.get_voice(user_id),
        "voice_info": get_voice_info(user_sessions.get_voice(user_id)),
    })


@bp.route("/api/settings", methods=["POST"])
def update_settings():
    """Update mode or voice."""
    user_id = get_user_id()
    data = request.get_json(silent=True) or {}

    if "mode" in data:
        mode = data["mode"].lower()
        valid_modes = [BotMode.TEXT, BotMode.VOICE, BotMode.VISION, BotMode.RAG]
        if mode not in valid_modes:
            return jsonify({"error": f"Unknown mode: {mode}"}), 400
        user_sessions.set_mode(user_id, mode)
        logger.info(f"User {user_id} switched to mode: {mode}")

    if "voice" in data:
        voice = data["voice"].lower()
        valid_voices = [
            VoiceType.ALLOY, VoiceType.ECHO, VoiceType.NOVA,
            VoiceType.FABLE, VoiceType.ONYX, VoiceType.SHIMMER,
        ]
        if voice not in valid_voices:
            return jsonify({"error": f"Unknown voice: {voice}"}), 400
        user_sessions.set_voice(user_id, voice)
        logger.info(f"User {user_id} switched to voice: {voice}")

    return jsonify({
        "mode": user_sessions.get_mode(user_id),
        "voice": user_sessions.get_voice(user_id),
    })


@bp.route("/api/reset", methods=["POST"])
def reset_history():
    """Clear conversation history."""
    user_id = get_user_id()
    user_sessions.clear_history(user_id)
    logger.info(f"User {user_id} cleared history")
    return jsonify({"ok": True, "message": "История диалога очищена"})


@bp.route("/api/stats", methods=["GET"])
def get_stats():
    """Return knowledge base statistics."""
    try:
        from rag.query import get_knowledge_base_stats
        stats = get_knowledge_base_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/chat", methods=["POST"])
def chat():
    """Handle text chat message."""
    user_id = get_user_id()
    data = request.get_json(silent=True) or {}
    text = (data.get("message") or "").strip()

    if not text:
        return jsonify({"error": "Сообщение не может быть пустым"}), 400

    try:
        response = run_async(route_text_request(user_id, text))
        result = {
            "text": response.get("text", ""),
            "mode": response.get("mode"),
            "has_image": response.get("has_image", False),
        }

        if response.get("has_image") and response.get("image_path"):
            image_path = Path(response["image_path"])
            dest = UPLOADS_DIR / image_path.name
            if image_path.exists() and image_path != dest:
                image_path.rename(dest)
                image_path = dest
            result["image_url"] = _media_url(image_path)
            result["revised_prompt"] = response.get("revised_prompt", "")

        mode = user_sessions.get_mode(user_id)
        if mode == BotMode.VOICE and not result.get("has_image"):
            voice_path = run_async(generate_voice_response(
                result["text"],
                voice=user_sessions.get_voice(user_id),
            ))
            dest = UPLOADS_DIR / voice_path.name
            if voice_path.exists() and voice_path != dest:
                voice_path.rename(dest)
                voice_path = dest
            result["audio_url"] = _media_url(voice_path)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return jsonify({"error": "Ошибка при обработке сообщения"}), 500


@bp.route("/api/image/generate", methods=["POST"])
def generate_image():
    """Generate image with DALL-E."""
    user_id = get_user_id()
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()

    if not prompt:
        return jsonify({"error": "Укажите описание изображения"}), 400

    try:
        response = run_async(route_image_generation_request(
            user_id=user_id,
            prompt=prompt,
            original_text=prompt,
        ))

        result = {"text": response.get("text", "")}

        if response.get("has_image") and response.get("image_path"):
            image_path = Path(response["image_path"])
            dest = UPLOADS_DIR / image_path.name
            if image_path.exists() and image_path != dest:
                image_path.rename(dest)
                image_path = dest
            result["image_url"] = _media_url(image_path)
            result["revised_prompt"] = response.get("revised_prompt", "")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Image generation error: {e}", exc_info=True)
        return jsonify({"error": "Ошибка генерации изображения"}), 500


@bp.route("/api/image/analyze", methods=["POST"])
def analyze_image():
    """Analyze uploaded image with Vision API."""
    user_id = get_user_id()

    if "image" not in request.files:
        return jsonify({"error": "Загрузите изображение"}), 400

    file = request.files["image"]
    caption = request.form.get("caption", "").strip() or None

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return jsonify({"error": f"Неподдерживаемый формат: {ext}"}), 400

    image_path = None
    try:
        image_path = _save_upload(file, UPLOADS_DIR, "img_")
        response = run_async(route_image_request(
            user_id=user_id,
            image_path=image_path,
            caption=caption,
        ))
        return jsonify({"text": response.get("text", "")})

    except Exception as e:
        logger.error(f"Image analysis error: {e}", exc_info=True)
        return jsonify({"error": "Ошибка анализа изображения"}), 500
    finally:
        cleanup_file(image_path)


@bp.route("/api/voice", methods=["POST"])
def voice_message():
    """Transcribe and respond to voice message."""
    user_id = get_user_id()

    if "audio" not in request.files:
        return jsonify({"error": "Загрузите аудиофайл"}), 400

    file = request.files["audio"]
    ext = Path(file.filename or "audio.webm").suffix.lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        return jsonify({"error": f"Неподдерживаемый формат: {ext}"}), 400

    voice_path = None
    audio_response_path = None
    image_path = None

    try:
        voice_path = _save_upload(file, UPLOADS_DIR, "voice_")
        response = run_async(route_voice_request(user_id, voice_path))

        if response.get("error"):
            return jsonify({
                "error": response.get("text", "Ошибка обработки голоса"),
                "details": response["error"],
            }), 500

        result = {
            "text": response.get("text", ""),
            "transcription": response.get("transcription", ""),
            "has_image": response.get("has_image", False),
        }

        if response.get("has_image") and response.get("image_path"):
            image_path = Path(response["image_path"])
            dest = UPLOADS_DIR / image_path.name
            if image_path.exists() and image_path != dest:
                image_path.rename(dest)
                image_path = dest
            result["image_url"] = _media_url(image_path)
            result["revised_prompt"] = response.get("revised_prompt", "")

        if response.get("voice_path"):
            audio_response_path = Path(response["voice_path"])
            dest = UPLOADS_DIR / audio_response_path.name
            if audio_response_path.exists() and audio_response_path != dest:
                audio_response_path.rename(dest)
                audio_response_path = dest
            result["audio_url"] = _media_url(audio_response_path)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Voice error: {e}", exc_info=True)
        return jsonify({"error": "Ошибка обработки голосового сообщения"}), 500
    finally:
        cleanup_files(voice_path, image_path)


@bp.route("/api/documents", methods=["POST"])
def upload_document():
    """Upload and index a document for RAG."""
    user_id = get_user_id()

    if "document" not in request.files:
        return jsonify({"error": "Загрузите документ"}), 400

    file = request.files["document"]
    ext = Path(file.filename or "").suffix.lower()

    if ext not in ALLOWED_DOC_EXTENSIONS:
        return jsonify({
            "error": "Поддерживаются: PDF, TXT, MD, DOCX"
        }), 400

    try:
        filename = secure_filename(file.filename or f"doc{ext}")
        file_path = DOCUMENTS_DIR / filename
        file.save(file_path)

        logger.info(f"User {user_id} uploaded document: {filename}")

        chunks = document_loader.load_document(file_path)
        vector_index.add_documents(chunks)

        return jsonify({
            "ok": True,
            "filename": filename,
            "chunks": len(chunks),
            "message": f"Документ «{filename}» проиндексирован ({len(chunks)} фрагментов)",
        })

    except Exception as e:
        logger.error(f"Document upload error: {e}", exc_info=True)
        return jsonify({"error": f"Ошибка загрузки: {e}"}), 500


@bp.route("/api/media/<filename>")
def serve_media(filename):
    """Serve uploaded/generated media files."""
    safe_name = secure_filename(filename)
    filepath = UPLOADS_DIR / safe_name
    if not filepath.exists():
        abort(404)
    return send_file(filepath)
