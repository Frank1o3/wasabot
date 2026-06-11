"""
AI pipeline orchestrating prompt building, Groq LLM, markers, and database.

🐍 PYTHON NATIVE: Async orchestration with explicit type hints and structured error handling
👤 HUMANITY FEATURE: Typing indicators, contextual replies, read receipts
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
import random
from typing import Any
import uuid

from groq import Groq

from wasabot.config import get_settings
from wasabot.services.db import (
    add_conversation,
    add_relationship,
    add_task,
    load_conversation,
    load_profile,
    profile_exists,
    save_profile,
)
from wasabot.services.logger import get_correlation_id, get_logger
from wasabot.services.markers import CONTEXTUAL_REPLY_RE, calculate_execute_at, extract_markers
from wasabot.services.prompt_builder import (
    build_system_prompt,
    build_user_context_for_ai,
    enrich_profile_from_conversation,
    update_profile_with_context,
)

logger = get_logger(__name__)


def spawn(coro: Coroutine[Any, Any, Any]) -> None:
    """Spawn a background task with error handling."""
    import asyncio

    task = asyncio.create_task(coro)

    def _done(task: asyncio.Task[Any]) -> None:
        try:
            task.result()
        except Exception as e:
            logger.error(f"background_task_failed | error={e!s}")

    task.add_done_callback(_done)


# 🎬 DELAYED VIDEO: Rickroll video URL for delayed sends
RICKROLL_URL = "https://cdn.mtdv.me/video/rick.mp4"
# Default caption for delayed videos
DELAYED_VIDEO_CAPTION = "👀 aquí está lo que pediste"


class AIPipelineResult:
    """Result of AI pipeline processing."""

    def __init__(
        self,
        reply: str,
        send_video: bool = False,
        video_url: str | None = None,
        send_delayed_video: bool = False,
        delayed_video_url: str | None = None,
        schedule_delay_seconds: int | None = None,
        scheduled_message: str | None = None,
        reply_to_message_id: str | None = None,  # 👤 HUMANITY FEATURE: Contextual reply target
    ) -> None:
        self.reply = reply
        self.send_video = send_video
        self.video_url = video_url
        # 🎬 DELAYED VIDEO: New fields for delayed video support
        self.send_delayed_video = send_delayed_video
        self.delayed_video_url = delayed_video_url
        self.schedule_delay_seconds = schedule_delay_seconds
        self.scheduled_message = scheduled_message
        self.reply_to_message_id = reply_to_message_id  # 🐍 FIX: conditional contextual reply


class AIPipeline:
    """
    Main AI processing pipeline.
    Flow:
    1. Load user profile and conversation history
    2. Build system prompt with context
    3. Call Groq LLM
    4. Extract markers from response
    5. Strip markers and save clean reply to history
    6. Schedule tasks if needed
    7. Return clean reply + actions
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = Groq(api_key=self._settings.groq_api_key)
        self._model = self._settings.groq_model

    async def process_message(
        self,
        wa_id: str,
        user_message: str,
        is_group: bool = False,
        incoming_message_id: str | None = None,
    ) -> AIPipelineResult | None:
        """
        Process a user message through the full AI pipeline.

        Args:
            wa_id: User's WhatsApp ID
            user_message: The message text from user
            is_group: Whether this is a group conversation

            incoming_message_id: 👤 HUMANITY FEATURE: Message ID for contextual replies

        Returns:
            AIPipelineResult with reply and actions, or None on failure
        """
        correlation_id = get_correlation_id() or ""

        try:
            # Step 1: Load profile and check if new user
            profile = load_profile(wa_id)
            is_new_user = not profile_exists(wa_id)

            if is_new_user:
                logger.info(f"new_user_detected | wa_id={wa_id}")

            # Step 2: Load conversation history
            history = load_conversation(wa_id, limit=10)

            # Step 3: Build system prompt
            system_prompt = build_system_prompt(profile, user_message, is_group)

            # 👤 HUMANITY FEATURE: Add context about people mentioned in the conversation
            # This allows the AI to talk about users as if it really knows them
            import re

            person_name_match = re.search(
                r"(?:qu[eí]n es|qui[eé]n es|sabes de|conoces a|hablemos de|habla(?:me)?\s+de|háblame\s+de|háblame\s+sobre|quiero\s+saber\s+de|dime\s+de)\s+([A-Za-zÀ-ÿ]+)",
                user_message,
                re.IGNORECASE | re.UNICODE,
            )
            if person_name_match:
                person_name = person_name_match.group(1).strip()
                person_context = build_user_context_for_ai(wa_id, person_name)
                if person_context:
                    system_prompt += person_context
                    logger.info(f"person_context_added | person={person_name} | wa_id={wa_id}")

            # Step 4: Build messages array for Groq
            messages = [{"role": "system", "content": system_prompt}]

            # Add conversation history
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})

            # Add current user message
            messages.append({"role": "user", "content": user_message})

            # Step 5: Call Groq LLM
            logger.debug(f"groq_request_starting | model={self._model}")

            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=300,  # Keep responses short
                temperature=0.8,  # Slightly creative for natural conversation
                stream=False,
            )

            ai_response = response.choices[0].message.content

            if not ai_response:
                logger.error("groq_empty_response")
                return None

            logger.info(f"groq_response_received | length={len(ai_response)}")

            # Step 6: Extract markers
            marker_result = extract_markers(ai_response)
            clean_reply = marker_result.cleaned_text

            # 👤 HUMANITY FEATURE: Detect contextual reply marker and conditionally set reply_to_message_id
            # 🐍 FIX: conditional contextual reply - only use context when AI explicitly requests it
            use_contextual = bool(CONTEXTUAL_REPLY_RE.search(ai_response))
            if use_contextual:
                clean_reply = CONTEXTUAL_REPLY_RE.sub("", clean_reply).strip()
                reply_to_id = incoming_message_id
                logger.info(f"contextual_reply_detected | wa_id={wa_id}")
            else:
                reply_to_id = None  # DEFAULT: no context, prevents double-sending

            # ⏰ SAFETY NET: Auto-inject schedule marker if user requested scheduling but AI forgot the marker
            # Check for common Spanish scheduling phrases in the original user message
            scheduling_phrases = [
                "escríbeme en",
                "avísame en",
                "avísame luego",
                "recordatorio en",
                "en un minuto",
                "en unos minutos",
                "en una hora",
                "luego me",
                "después me",
                "más tarde",
                "en un rato",
                "en breve",
                "pronto",
            ]
            user_asked_for_schedule = any(
                phrase in user_message.lower() for phrase in scheduling_phrases
            )

            # If user asked for scheduling but AI didn't include marker, auto-inject it
            if user_asked_for_schedule and marker_result.schedule_delay_seconds is None:
                # Default to 1 minute (60 seconds) as a reasonable fallback
                marker_result.schedule_delay_seconds = 60
                marker_result.scheduled_message = clean_reply
                logger.info(
                    f"scheduling_marker_auto_injected | wa_id={wa_id} | reason=user_requested_but_ai_omitted"
                )

            # Step 7: Save conversation to history (clean reply, no markers)
            add_conversation(wa_id, "user", user_message)
            add_conversation(wa_id, "assistant", clean_reply)

            # Step 8: Update profile if we extracted new info (sync - name only)
            updated_profile = update_profile_with_context(profile, user_message, ai_response)
            if updated_profile:
                save_profile(
                    wa_id=wa_id,
                    name=updated_profile.get("name"),
                    traits=updated_profile.get("traits"),
                    topics=updated_profile.get("topics"),
                    notes=updated_profile.get("notes"),
                )

            # 👥 SOCIAL GRAPH: Extract and save relationships mentioned in conversation
            # This allows the AI to build a social network of who knows whom
            spawn(_extract_and_save_relationships(wa_id, user_message, ai_response))

            # Step 8b: Enrich profile with AI analysis (async - runs in background)
            # This fills traits, topics, notes, and status from conversation logs
            spawn(enrich_profile_from_conversation(wa_id, conversation_limit=20))

            # Step 9: Schedule tasks if markers present
            task_id = None

            # 🎬 DELAYED VIDEO: Handle delayed video scheduling (30-60 seconds random)
            if marker_result.send_delayed_video:
                task_id = str(uuid.uuid4())
                delay_seconds = random.randint(30, 60)  # Random delay between 30-60 seconds
                execute_at = calculate_execute_at(delay_seconds)

                execute_at = int(asyncio.get_event_loop().time()) + delay_seconds
                # Use Unix timestamp instead
                import time

                execute_at = int(time.time()) + delay_seconds

                # Use the video URL from marker or default to Rickroll
                video_url = marker_result.delayed_video_url or RICKROLL_URL

                add_task(
                    task_id=task_id,
                    wa_id=wa_id,
                    message="",  # Empty message for video tasks
                    execute_at=execute_at,
                    correlation_id=correlation_id,
                    is_group=is_group,
                    action="send_video",
                    video_url=video_url,
                    caption=DELAYED_VIDEO_CAPTION,
                )
                logger.info(
                    f"delayed_video_scheduled | task_id={task_id} | delay={delay_seconds}s | wa_id={wa_id}"
                )

            # Regular scheduled message
            elif marker_result.schedule_delay_seconds is not None:
                task_id = str(uuid.uuid4())
                execute_at = calculate_execute_at(marker_result.schedule_delay_seconds)

                import time

                execute_at = int(time.time()) + marker_result.schedule_delay_seconds

                add_task(
                    task_id=task_id,
                    wa_id=wa_id,
                    message=marker_result.scheduled_message or clean_reply,
                    execute_at=execute_at,
                    correlation_id=correlation_id,
                    is_group=is_group,
                )
                logger.info(
                    f"task_scheduled_via_marker | task_id={task_id} | delay={marker_result.schedule_delay_seconds}s"
                )

            # Step 10: Log result
            logger.info(
                f"ai_pipeline_completed | send_video={marker_result.send_video} | send_delayed_video={marker_result.send_delayed_video} | scheduled={task_id is not None}",
                extra={"meta": {"correlation_id": correlation_id}},
            )

            return AIPipelineResult(
                reply=clean_reply,
                send_video=marker_result.send_video,
                video_url=marker_result.video_url,
                send_delayed_video=marker_result.send_delayed_video,
                delayed_video_url=marker_result.delayed_video_url,
                schedule_delay_seconds=marker_result.schedule_delay_seconds,
                scheduled_message=marker_result.scheduled_message,
                reply_to_message_id=reply_to_id,  # 🐍 FIX: conditional contextual reply
            )

        except Exception as e:
            logger.error(
                f"ai_pipeline_failed | error={e!s}",
                extra={"meta": {"correlation_id": correlation_id}},
            )
            return None


# Global pipeline instance
_ai_pipeline: AIPipeline | None = None


def get_ai_pipeline() -> AIPipeline:
    """Get or create global AI pipeline."""
    global _ai_pipeline
    if _ai_pipeline is None:
        settings = get_settings()
        if settings.groq_api_key:
            _ai_pipeline = AIPipeline()
        else:
            logger.warning("ai_pipeline_unavailable | missing_groq_api_key")
            raise RuntimeError("Groq API key not configured for AI pipeline")
    return _ai_pipeline


async def process_user_message(
    wa_id: str,
    user_message: str,
    is_group: bool = False,
    incoming_message_id: str | None = None,
) -> AIPipelineResult | None:
    """
    Convenience function to process a message through the AI pipeline.

    This is the main entry point for webhook handlers.

    Args:
        wa_id: User's WhatsApp ID
        user_message: The message text
        is_group: Whether this is a group conversation

        incoming_message_id: 👤 HUMANITY FEATURE: Message ID for contextual replies

    Returns:
        AIPipelineResult or None on failure
    """
    pipeline = get_ai_pipeline()
    return await pipeline.process_message(wa_id, user_message, is_group, incoming_message_id)


async def _extract_and_save_relationships(
    wa_id: str,
    user_message: str,
    ai_response: str,
) -> None:
    """
    👥 SOCIAL GRAPH: Extract people mentioned in conversation and save relationships.

    This function analyzes both the user message and AI response to identify
    names of people being discussed, then records these relationships in the database.
    This allows the AI to build a social network and talk about people contextually.

    Example: If Juan talks to the bot about Pablo, we record that Juan knows Pablo.
    Later, when anyone asks about Pablo, the bot can use this info.
    """
    import re

    logger = get_logger(__name__)

    try:
        # Common patterns for mentioning people in Spanish
        person_patterns = [
            # "habla de [nombre]", "háblame de [nombre]", "quién es [nombre]"
            r"(?:qu[eí]n es|qui[eé]n es|sabes de|conoces a|hablemos de|habla(?:me)?\s+de|háblame\s+de|háblame\s+sobre|quiero\s+saber\s+de|dime\s+de)\s+([A-Za-zÀ-ÿ]+)",
            # "[nombre] dijo", "[nombre] me contó"
            r"([A-Z][a-zÀ-ÿ]+)\s+(?:dijo|contó|comentó|mencionó|habló)",
            # "mi amigo [nombre]", "mi pana [nombre]"
            r"(?:mi\s+(?:amigo|pana|hermano|primo|vecino|compañero))\s+([A-Z][a-zÀ-ÿ]+)",
            # Simple mentions: "Pablo está...", "Vi a María..."
            r"(?:Vi\s+a|Estuve\s+con|Fui\s+a\s+ver\s+a|Quedé\s+con)\s+([A-Z][a-zÀ-ÿ]+)",
        ]

        extracted_names = set()

        # Search in both user message and AI response
        for text in [user_message, ai_response]:
            for pattern in person_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE | re.UNICODE)
                for match in matches:
                    name = match.strip()
                    # Filter out common false positives
                    if name.lower() not in ["que", "quien", "como", "cuando", "donde", "por"]:
                        extracted_names.add(name)

        # Save each relationship found
        for person_name in extracted_names:
            # Try to capitalize properly
            person_name_formatted = person_name.capitalize()

            add_relationship(
                user_wa_id=wa_id,
                person_name=person_name_formatted,
                context=f"Mencionado en conversación: {user_message[:100]}",
            )

            logger.info(f"relationship_extracted | user={wa_id} | person={person_name_formatted}")

        if extracted_names:
            logger.info(
                f"relationships_extraction_complete | user={wa_id} | count={len(extracted_names)}"
            )

    except Exception as e:
        logger.error(f"relationship_extraction_failed | error={e!s}")
