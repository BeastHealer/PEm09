"""
Tests for Speech-to-Text functionality.
"""

import pytest
from unittest.mock import AsyncMock, patch, Mock
from pathlib import Path

from services.stt import transcribe_voice_message
from services.openai_client import OpenAIClient, openai_client


@pytest.fixture
def mock_wav_file(tmp_path):
    """Create a mock WAV file."""
    wav_file = tmp_path / "test_audio.wav"
    wav_file.write_bytes(b"fake wav data")
    return wav_file


@pytest.fixture
def mock_ogg_file(tmp_path):
    """Create a mock OGG file."""
    ogg_file = tmp_path / "test_audio.ogg"
    ogg_file.write_bytes(b"fake audio data")
    return ogg_file


@pytest.fixture
def mock_transcribe():
    """Mock transcription on the shared OpenAI client."""
    with patch.object(
        openai_client,
        "transcribe_audio",
        new_callable=AsyncMock,
        return_value="Transcribed text from audio",
    ) as mock:
        yield mock


class TestSTT:
    """Test suite for Speech-to-Text."""

    @pytest.mark.asyncio
    async def test_transcribe_audio_basic(self, mock_wav_file):
        """Test basic audio transcription."""
        client = OpenAIClient()
        mock_response = Mock(text="Transcribed text from audio")

        with patch.object(
            client.client.audio.transcriptions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.transcribe_audio(mock_wav_file)

        assert isinstance(result, str)
        assert result == "Transcribed text from audio"

    @pytest.mark.asyncio
    async def test_transcribe_voice_message_wav(self, mock_wav_file, mock_transcribe):
        """Test transcribing WAV voice message."""
        result = await transcribe_voice_message(mock_wav_file)

        assert isinstance(result, str)
        assert result == "Transcribed text from audio"
        mock_transcribe.assert_awaited_once_with(mock_wav_file)

    @pytest.mark.asyncio
    async def test_transcribe_voice_message_ogg(self, mock_ogg_file, mock_transcribe):
        """Test transcribing OGG voice message without conversion."""
        result = await transcribe_voice_message(mock_ogg_file)

        assert isinstance(result, str)
        assert result == "Transcribed text from audio"
        mock_transcribe.assert_awaited_once_with(mock_ogg_file)


class TestAudioHelpers:
    """Test suite for audio helper functions."""

    def test_convert_ogg_to_wav_mock(self, tmp_path):
        """Test OGG to WAV conversion (mocked)."""
        from utils.helpers import convert_ogg_to_wav

        input_path = tmp_path / "test.ogg"
        input_path.write_bytes(b"fake ogg")

        with patch("pydub.AudioSegment") as mock_audio:
            mock_segment = Mock()
            mock_audio.from_file.return_value = mock_segment

            result = convert_ogg_to_wav(input_path)

            assert result.suffix == ".wav"
            assert result.stem == input_path.stem
            mock_segment.export.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_file_async(self, tmp_path):
        """Test async file saving."""
        from utils.helpers import save_file_async

        content = b"test content"
        result = await save_file_async(content, "txt")

        assert result.exists()
        assert result.suffix == ".txt"
        result.unlink()

    def test_cleanup_file(self, tmp_path):
        """Test file cleanup."""
        from utils.helpers import cleanup_file

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        assert test_file.exists()

        cleanup_file(test_file)
        assert not test_file.exists()

    def test_cleanup_multiple_files(self, tmp_path):
        """Test cleanup of multiple files."""
        from utils.helpers import cleanup_files

        file1 = tmp_path / "test1.txt"
        file2 = tmp_path / "test2.txt"
        file1.write_text("test1")
        file2.write_text("test2")

        cleanup_files(file1, file2)
        assert not file1.exists()
        assert not file2.exists()


class TestTTSIntegration:
    """Test suite for TTS integration."""

    @pytest.fixture
    def mock_generate_speech(self, tmp_path):
        """Mock speech generation on the shared OpenAI client."""
        output = tmp_path / "speech.mp3"
        output.write_bytes(b"fake audio")

        with patch.object(
            openai_client,
            "generate_speech",
            new_callable=AsyncMock,
            return_value=output,
        ) as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_generate_speech(self, mock_generate_speech):
        """Test speech generation."""
        from services.tts import generate_voice_response

        result = await generate_voice_response("Hello, this is a test", voice="alloy")

        assert isinstance(result, Path)
        mock_generate_speech.assert_awaited_once()

    def test_get_voice_info(self):
        """Test voice information retrieval."""
        from services.tts import get_voice_info

        info = get_voice_info("nova")
        assert "name" in info
        assert "type" in info
        assert "description" in info

    def test_get_available_voices(self):
        """Test available voices listing."""
        from services.tts import get_available_voices

        voices = get_available_voices()
        assert isinstance(voices, str)
        assert "alloy" in voices.lower()
        assert "nova" in voices.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
