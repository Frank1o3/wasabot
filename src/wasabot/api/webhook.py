# src/wasabot/webhook.py
"""
WhatsApp webhook handler with AI pipeline integration.

🐍 PYTHON NATIVE: FastAPI BackgroundTasks for async processing, 3-second response guarantee
👤 HUMANITY FEATURE: Typing indicators, contextual replies, read receipts
"""

import asyncio
import random
import secrets

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import PlainTextResponse

from wasabot.analyzer import analyze_payload_safe, get_message_summary
from wasabot.config import get_settings
from wasabot.models.webhook import Message
from wasabot.services.ai_pipeline import process_user_message
from wasabot.services.db import save_profile
from wasabot.services.logger import (
    CorrelationContext,
    get_logger,
    set_correlation_id,
    setup_logging,
)
from wasabot.services.typing import mark_message_read, send_typing_indicator
from wasabot.services.voice import get_voice_service
from wasabot.services.whatsapp_api import get_whatsapp_client

logger = get_logger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])

# Initialize logging on module load
setup_logging()

logger.info("webhook_module_loaded")
# Note: Scheduler is started by the main app (app.py) when uvicorn runs


@router.get("/")
async def webhook_get(request: Request) -> PlainTextResponse:
    """
    WhatsApp/Meta webhook verification endpoint.
    Handles GET requests with hub.mode, hub.challenge, hub.verify_token params.
    """
    from wasabot.config import get_settings

    params = dict(request.query_params)
    mode = params.get("hub.mode") or params.get("hub_mode")
    challenge = params.get("hub.challenge") or params.get("hub_challenge")
    verify_token = params.get("hub.verify_token") or params.get("hub_verify_token")

    settings = get_settings()
    wa_verify_token = settings.wa_verify_token

    # Validate required params
    if not mode or not challenge or not verify_token:
        logger.warning("webhook_verification_missing_params")
        return PlainTextResponse(content="Missing parameters", status_code=400)

    # Only "subscribe" is valid for verification
    if mode != "subscribe":
        logger.warning(f"webhook_verification_invalid_mode | mode={mode}")
        return PlainTextResponse(content="Invalid mode", status_code=400)

    # Constant-time token comparison (prevents timing attacks)
    if wa_verify_token and secrets.compare_digest(verify_token, wa_verify_token):
        logger.info("webhook_verified_success")
        return PlainTextResponse(content=challenge, status_code=200)

    # Failed verification - minimal logging in prod
    logger.warning(
        f"webhook_verification_failed | "
        f"received={(verify_token or '')[:4]}... | "
        f"expected={(wa_verify_token or '')[:4] if wa_verify_token else 'NOT_SET'}..."
    )

    return PlainTextResponse(content="Verification failed", status_code=403)


async def _process_text_message(
    wa_id: str,
    message_body: str,
    correlation_id: str,
    is_group: bool = False,
    incoming_message_id: str | None = None,
) -> None:
    """
    Process a text message through the AI pipeline.

    This runs in the background to ensure webhook responds within 3 seconds.

    👤 HUMANITY FEATURE: Shows typing indicator, marks message as read, sends contextual reply
    """
    with CorrelationContext(correlation_id):
        try:
            logger.info(f"text_message_processing | wa_id={wa_id}")

            # Ensure profile exists (basic initialization)
            save_profile(wa_id=wa_id)

            # Process through AI pipeline
            result = await process_user_message(wa_id, message_body, is_group, incoming_message_id)

            if result is None:
                logger.error(f"ai_pipeline_returned_none | wa_id={wa_id}")
                return

            # Send reply via WhatsApp API
            whatsapp_client = get_whatsapp_client()

            # Send text reply
            await whatsapp_client.send_text(wa_id, result.reply)

            # 👤 HUMANITY FEATURE: Calculate typing delay based on reply length
            # 25 chars/sec, capped at 15s, with ±10% jitter for human feel
            reply_length = len(result.reply)
            base_delay_ms = min(reply_length / 25 * 1000, 15000)
            jitter = random.uniform(-0.1, 0.1) * base_delay_ms
            typing_delay_ms = max(base_delay_ms + jitter, 1000)  # Minimum 1s

            # Safety cap: if AI generation already took >8s, cap delay at 3s
            # (We can't measure exact AI time here, so we just cap total delay)
            typing_delay_ms = min(typing_delay_ms, 15000)
            typing_delay_seconds = typing_delay_ms / 1000

            # 👤 HUMANITY FEATURE: Send typing indicator (fire-and-forget)
            if incoming_message_id:
                settings = get_settings()
                asyncio.create_task(
                    send_typing_indicator(
                        settings.wa_phone_number_id,
                        settings.wa_access_token,
                        incoming_message_id,
                    )
                )

                # Wait for typing delay before sending reply
                await asyncio.sleep(typing_delay_seconds)

            # Send text reply with contextual reference
            await whatsapp_client.send_text(
                wa_id,
                result.reply,
                reply_to_message_id=incoming_message_id,  # 👤 HUMANITY FEATURE: Contextual reply
            )

            # Send video if marker was present (immediate, not delayed)
            if result.send_video:
                video_url = result.video_url
                if video_url:
                    await whatsapp_client.send_video(
                        wa_id,
                        video_url,
                        caption=result.reply,
                        reply_to_message_id=incoming_message_id,  # 👤 HUMANITY FEATURE: Contextual reply
                    )
                else:
                    logger.warning(f"video_marker_without_url | wa_id={wa_id}")

            logger.info(
                f"text_message_completed | wa_id={wa_id} | reply_length={len(result.reply)}"
            )

        except Exception as e:
            logger.error(f"text_message_processing_failed | error={e!s}")


async def _process_voice_message(
    wa_id: str,
    media_url: str,
    correlation_id: str,
    is_group: bool = False,
) -> None:
    """
    Process a voice message: download → transcribe → AI pipeline.

    This runs in the background to ensure webhook responds within 3 seconds.
    """
    with CorrelationContext(correlation_id):
        try:
            logger.info(f"voice_message_processing | wa_id={wa_id}")

            # Ensure profile exists
            save_profile(wa_id=wa_id)

            # Download audio from WhatsApp
            whatsapp_client = get_whatsapp_client()
            audio_data = await whatsapp_client.download_media(media_url)

            if audio_data is None:
                logger.error("voice_download_failed | wa_id={wa_id}")
                return

            # Transcribe with Groq Whisper
            voice_service = get_voice_service()
            transcribed_text = await voice_service.transcribe_audio(audio_data)

            if not transcribed_text:
                logger.warning("voice_transcription_empty | wa_id={wa_id}")
                # Send acknowledgment even if transcription failed
                await whatsapp_client.send_text(wa_id, "No escuché bien, ¿puedes repetir? 🤷")
                return

            logger.info(f"voice_transcribed | wa_id={wa_id} | text='{transcribed_text[:50]}...'")

            # Process transcribed text through AI pipeline
            result = await process_user_message(wa_id, transcribed_text, is_group)

            if result is None:
                logger.error("ai_pipeline_returned_none | wa_id={wa_id}")
                return

            # Send reply
            await whatsapp_client.send_text(wa_id, result.reply)

            # Send video if marker was present
            if result.send_video:
                video_url = result.video_url
                if video_url:
                    await whatsapp_client.send_video(wa_id, video_url, caption=result.reply)

            logger.info(f"voice_message_completed | wa_id={wa_id}")

        except Exception as e:
            logger.error(f"voice_message_processing_failed | error={e!s}")


# 🚀 FUTURE CAPABILITY: Stub handlers for new message types


async def _handle_sticker_message(msg: Message, correlation_id: str) -> None:
    """
    🚀 FUTURE CAPABILITY: Process sticker — download, react, or ignore based on persona.

    TODO: Implement full sticker handling logic.
    """
    logger.info(
        "sticker_received",
        extra={
            "meta": {
                "correlation_id": correlation_id,
                "animated": msg.sticker.animated if msg.sticker else None,
            }
        },
    )


async def _handle_reaction_message(msg: Message, correlation_id: str) -> None:
    """
    🚀 FUTURE CAPABILITY: React to reactions — e.g., acknowledge with emoji or ignore.

    TODO: Implement full reaction handling logic.
    """
    emoji = msg.reaction.emoji if msg.reaction else "❌"
    target_msg_id = msg.reaction.message_id if msg.reaction else None
    logger.info(
        "reaction_received",
        extra={
            "meta": {
                "correlation_id": correlation_id,
                "emoji": emoji,
                "target_msg_id": target_msg_id,
            }
        },
    )


async def _handle_edit_message(msg: Message, correlation_id: str) -> None:
    """
    🚀 FUTURE CAPABILITY: Handle message edits — update conversation history or ignore.

    TODO: Implement full edit handling logic.
    """
    original_id = msg.edit.original_message_id if msg.edit else None
    logger.info(
        "message_edited",
        extra={"meta": {"correlation_id": correlation_id, "original_id": original_id}},
    )


@router.post("/")
async def webhook_post(request: Request, background_tasks: BackgroundTasks) -> PlainTextResponse:
    """
    WhatsApp webhook POST handler.

    🐍 PYTHON NATIVE: Uses FastAPI BackgroundTasks to ensure <3s response time
    while heavy processing happens asynchronously.

    👤 HUMANITY FEATURE: Marks messages as read immediately, passes message ID for contextual replies
    """
    # Generate correlation ID for this webhook
    correlation_id = set_correlation_id()

    try:
        raw_payload = await request.json()

        # Parse with analyzer for typed access
        payload = analyze_payload_safe(raw_payload)

        if payload is None:
            logger.error("payload_parse_failed", extra={"meta": {"correlation_id": correlation_id}})
            return PlainTextResponse(content="Invalid payload", status_code=400)

        # Log summary
        summary = get_message_summary(payload)
        logger.info(
            f"webhook_received | {summary}", extra={"meta": {"correlation_id": correlation_id}}
        )

        # Process each message type
        messages_processed = 0

        # Text messages
        for msg in payload.text_messages:
            user_id = msg.from_
            body = msg.text.body if msg.text else ""
            is_group = msg.is_group_message

            # 👤 HUMANITY FEATURE: Extract message ID for contextual replies and read receipts
            message_id = msg.id

            logger.info(f"text_message_queued | from={user_id} | body='{body[:50]}...'")

            # Offload to background task

            # 👤 HUMANITY FEATURE: Mark message as read immediately (fire-and-forget)
            settings = get_settings()
            asyncio.create_task(
                mark_message_read(
                    settings.wa_phone_number_id,
                    settings.wa_access_token,
                    message_id,
                )
            )

            # Offload to background task with message ID for contextual replies
            background_tasks.add_task(
                _process_text_message,
                user_id,
                body,
                correlation_id,
                is_group,
                message_id,  # 👤 HUMANITY FEATURE: Pass message ID for contextual reply
            )
            messages_processed += 1

        # Voice messages
        for msg in payload.voice_messages:
            if msg.audio and msg.audio.url:
                user_id = msg.from_
                media_url = msg.audio.url
                is_group = msg.is_group_message

                # 👤 HUMANITY FEATURE: Extract message ID for read receipts
                message_id = msg.id

                logger.info(f"voice_message_queued | from={user_id} | media_id={msg.audio.id}")

                # 👤 HUMANITY FEATURE: Mark message as read immediately (fire-and-forget)
                settings = get_settings()
                asyncio.create_task(
                    mark_message_read(
                        settings.wa_phone_number_id,
                        settings.wa_access_token,
                        message_id,
                    )
                )

                # Offload to background task
                background_tasks.add_task(
                    _process_voice_message,
                    user_id,
                    media_url,
                    correlation_id,
                    is_group,
                )
                messages_processed += 1

        # 🚀 FUTURE CAPABILITY: Route new message types to stub handlers
        # These handlers log the event and return quickly without blocking

        # Get all messages from payload for iterating new types
        all_messages = payload.all_messages

        for msg in all_messages:
            # Skip already processed text and voice messages
            if msg.is_text or msg.is_voice or msg.is_audio:
                continue

            user_id = msg.from_
            is_group = msg.is_group_message

            # Route by message type
            if msg.is_sticker:
                logger.info(f"sticker_message_queued | from={user_id}")
                background_tasks.add_task(_handle_sticker_message, msg, correlation_id)
                messages_processed += 1
            elif msg.is_reaction:
                logger.info(f"reaction_message_queued | from={user_id}")
                background_tasks.add_task(_handle_reaction_message, msg, correlation_id)
                messages_processed += 1
            elif msg.is_edit:
                logger.info(f"edit_message_queued | from={user_id}")
                background_tasks.add_task(_handle_edit_message, msg, correlation_id)
                messages_processed += 1
            else:
                # Unknown message type - just log
                logger.debug(f"unknown_message_type | from={user_id} | type={msg.type}")

        logger.info(f"webhook_processing_complete | messages_queued={messages_processed}")

        # Return immediately - background tasks continue processing
        return PlainTextResponse(content="Event received", status_code=200)

    except Exception as e:
        logger.error(f"webhook_handler_failed | error={e!s}")
        return PlainTextResponse(content="Internal error", status_code=500)
