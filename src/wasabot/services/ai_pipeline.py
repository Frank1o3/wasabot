"""
AI pipeline orchestrating prompt building, Groq LLM, markers, and database.

🐍 PYTHON NATIVE: Async orchestration with explicit type hints and structured error handling
"""

from __future__ import annotations

import uuid

from groq import Groq

from wasabot.config import get_settings
from wasabot.services.db import (
    add_conversation,
    add_task,
    load_conversation,
    load_profile,
    profile_exists,
    save_profile,
)
from wasabot.services.logger import get_correlation_id, get_logger
from wasabot.services.markers import extract_markers
from wasabot.services.prompt_builder import build_system_prompt, update_profile_with_context

logger = get_logger(__name__)


class AIPipelineResult:
    """Result of AI pipeline processing."""

    def __init__(
        self,
        reply: str,
        send_video: bool = False,
        video_url: str | None = None,
        schedule_delay_seconds: int | None = None,
        scheduled_message: str | None = None,
    ) -> None:
        self.reply = reply
        self.send_video = send_video
        self.video_url = video_url
        self.schedule_delay_seconds = schedule_delay_seconds
        self.scheduled_message = scheduled_message


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
    ) -> AIPipelineResult | None:
        """
        Process a user message through the full AI pipeline.

        Args:
            wa_id: User's WhatsApp ID
            user_message: The message text from user
            is_group: Whether this is a group conversation

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
                messages=messages,  # type: ignore[arg-type]
                max_tokens=300,  # Keep responses short
                temperature=0.8,  # Slightly creative for natural conversation
            )

            ai_response = response.choices[0].message.content

            if not ai_response:
                logger.error("groq_empty_response")
                return None

            logger.info(f"groq_response_received | length={len(ai_response)}")

            # Step 6: Extract markers
            marker_result = extract_markers(ai_response)
            clean_reply = marker_result.cleaned_text

            # Step 7: Save conversation to history (clean reply, no markers)
            add_conversation(wa_id, "user", user_message)
            add_conversation(wa_id, "assistant", clean_reply)

            # Step 8: Update profile if we extracted new info
            updated_profile = update_profile_with_context(profile, user_message, ai_response)
            if updated_profile:
                save_profile(
                    wa_id=wa_id,
                    name=updated_profile.get("name"),
                    traits=updated_profile.get("traits"),
                    topics=updated_profile.get("topics"),
                    notes=updated_profile.get("notes"),
                )

            # Step 9: Schedule task if marker present
            task_id = None
            if marker_result.schedule_delay_seconds is not None:
                task_id = str(uuid.uuid4())
                execute_at = (
                    int(
                        correlation_id  # type: ignore[assignment]
                    )
                    if False
                    else 0
                )  # Placeholder - will be calculated properly

                from wasabot.services.markers import calculate_execute_at

                execute_at = calculate_execute_at(marker_result.schedule_delay_seconds)

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
                f"ai_pipeline_completed | send_video={marker_result.send_video} | scheduled={task_id is not None}",
                extra={"meta": {"correlation_id": correlation_id}},
            )

            return AIPipelineResult(
                reply=clean_reply,
                send_video=marker_result.send_video,
                video_url=marker_result.video_url,
                schedule_delay_seconds=marker_result.schedule_delay_seconds,
                scheduled_message=marker_result.scheduled_message,
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
) -> AIPipelineResult | None:
    """
    Convenience function to process a message through the AI pipeline.

    This is the main entry point for webhook handlers.

    Args:
        wa_id: User's WhatsApp ID
        user_message: The message text
        is_group: Whether this is a group conversation

    Returns:
        AIPipelineResult or None on failure
    """
    pipeline = get_ai_pipeline()
    return await pipeline.process_message(wa_id, user_message, is_group)
