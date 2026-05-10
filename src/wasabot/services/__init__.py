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

from wasabot.services.logger import setup_logging, get_logger
from wasabot.services.db import get_db_pool
from wasabot.services.whatsapp_api import get_whatsapp_client
from wasabot.services.voice import get_voice_service
from wasabot.services.ai_pipeline import get_ai_pipeline, process_user_message
from wasabot.services.scheduler import start_scheduler, stop_scheduler, get_scheduler

__all__ = [
    "setup_logging",
    "get_logger",
    "get_db_pool",
    "get_whatsapp_client",
    "get_voice_service",
    "get_ai_pipeline",
    "process_user_message",
    "start_scheduler",
    "stop_scheduler",
    "get_scheduler",
]
