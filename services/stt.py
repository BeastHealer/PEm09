"""
Speech-to-Text Service.
Handles voice message transcription via Whisper (ProxyAPI).
"""

from pathlib import Path
from typing import Union

from services.openai_client import openai_client
from utils.logging import logger
from utils.helpers import convert_audio_to_wav, cleanup_file

# Formats supported by Whisper API without conversion
WHISPER_NATIVE_FORMATS = {
    ".flac", ".m4a", ".mp3", ".mp4", ".mpeg", ".mpga",
    ".oga", ".ogg", ".wav", ".webm",
}


async def transcribe_voice_message(audio_path: Union[str, Path]) -> str:
    """
    Transcribe a voice message to text.

    Whisper accepts webm/ogg/mp3/wav directly — no FFmpeg required for these.
    """
    audio_path = Path(audio_path)
    wav_path = None

    try:
        suffix = audio_path.suffix.lower()

        if suffix in WHISPER_NATIVE_FORMATS:
            logger.debug(f"Transcribing directly ({suffix}): {audio_path}")
            text = await openai_client.transcribe_audio(audio_path)
        else:
            logger.debug(f"Converting {suffix} to WAV for Whisper: {audio_path}")
            wav_path = convert_audio_to_wav(audio_path)
            text = await openai_client.transcribe_audio(wav_path)

        logger.info(f"Transcription completed: {len(text)} characters")
        return text

    except Exception as e:
        logger.error(f"Error in voice transcription: {e}")
        raise

    finally:
        if wav_path and wav_path != audio_path:
            cleanup_file(wav_path)

