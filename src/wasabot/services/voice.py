"""
Voice transcription service using Groq Whisper.

🐍 PYTHON NATIVE: Groq SDK for STT, async file handling
"""

from __future__ import annotations

import io

from groq import Groq

from wasabot.config import get_settings
from wasabot.services.logger import get_correlation_id, get_logger

logger = get_logger(__name__)


class VoiceService:
    """Speech-to-text service using Groq Whisper."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = Groq(api_key=self._settings.groq_api_key)
        self._model = self._settings.groq_whisper_model

    async def transcribe_audio(self, audio_data: bytes) -> str | None:
        """
        Transcribe audio data to text.

        Args:
            audio_data: Raw audio bytes (OGG/OPUS format from WhatsApp)

        Returns:
            Transcribed text or None on failure
        """
        correlation_id = get_correlation_id() or ""

        try:
            # Create file-like object from bytes
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "audio.ogg"  # WhatsApp voice notes are OGG

            # Call Groq Whisper API
            transcription = self._client.audio.transcriptions.create(
                file=audio_file,
                model=self._model,
                language="es",  # Spanish for Dominican Republic
                response_format="text",
            )

            if transcription:
                logger.info(f"voice_transcribed | length={len(transcription)}")
                return transcription.strip()
            else:
                logger.warning("voice_transcription_empty")
                return None

        except Exception as e:
            logger.error(
                f"voice_transcription_failed | error={e!s}",
                extra={"meta": {"correlation_id": correlation_id}},
            )
            return None

    async def transcribe_audio_file(self, file_path: str) -> str | None:
        """
        Transcribe audio from a file path.

        Args:
            file_path: Path to audio file

        Returns:
            Transcribed text or None on failure
        """
        correlation_id = get_correlation_id() or ""

        try:
            with open(file_path, "rb") as f:
                audio_data = f.read()

            return await self.transcribe_audio(audio_data)

        except FileNotFoundError:
            logger.error(
                f"voice_file_not_found | path={file_path}",
                extra={"meta": {"correlation_id": correlation_id}},
            )
            return None
        except Exception as e:
            logger.error(
                f"voice_transcription_failed | error={e!s}",
                extra={"meta": {"correlation_id": correlation_id}},
            )
            return None


# Global service instance
_voice_service: VoiceService | None = None


def get_voice_service() -> VoiceService:
    """Get or create global voice service."""
    global _voice_service
    if _voice_service is None:
        settings = get_settings()
        if settings.groq_api_key:
            _voice_service = VoiceService()
        else:
            logger.warning("voice_service_unavailable | missing_groq_api_key")
            raise RuntimeError("Groq API key not configured for voice service")
    return _voice_service
