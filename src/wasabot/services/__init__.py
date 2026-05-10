"""
Wasabot services package.

Contains core business logic services:
- logger: Structured JSON logging with correlation IDs
- db: SQLite database with thread-safe connection pooling
- prompt_builder: AI system prompt construction
- markers: Regex-based marker extraction
- whatsapp_api: Async WhatsApp Cloud API client
- voice: Groq Whisper speech-to-text
- ai_pipeline: Main AI orchestration pipeline
- scheduler: APScheduler background task polling
"""

from wasabot.services.ai_pipeline import get_ai_pipeline, process_user_message
from wasabot.services.db import get_db_pool
from wasabot.services.logger import get_logger, setup_logging
from wasabot.services.scheduler import get_scheduler, start_scheduler, stop_scheduler
from wasabot.services.voice import get_voice_service
from wasabot.services.whatsapp_api import get_whatsapp_client

__all__ = [
    "get_ai_pipeline",
    "get_db_pool",
    "get_logger",
    "get_scheduler",
    "get_voice_service",
    "get_whatsapp_client",
    "process_user_message",
    "setup_logging",
    "start_scheduler",
    "stop_scheduler",
]
