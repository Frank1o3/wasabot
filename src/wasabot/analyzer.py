# src/wasabot/analyzer.py
"""
WhatsApp Webhook Payload Analyzer

Parses raw JSON payloads into typed Pydantic models for safe, IDE-friendly access.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from wasabot.models.webhook import WebhookPayload


class WebhookAnalysisError(Exception):
    """Raised when webhook payload parsing fails."""


def analyze_payload(raw_payload: dict[str, Any]) -> WebhookPayload:
    """
    Parse a raw WhatsApp webhook JSON payload into a typed WebhookPayload object.

    Args:
        raw_payload: The decoded JSON dict from the webhook POST request.

    Returns:
        WebhookPayload: A validated, typed object with IDE autocompletion.

    Raises:
        WebhookAnalysisError: If the payload is invalid or missing required fields.
    """
    try:
        return WebhookPayload.model_validate(raw_payload)
    except ValidationError as e:
        raise WebhookAnalysisError(f"Invalid webhook payload: {e}") from e


def analyze_payload_safe(raw_payload: dict[str, Any]) -> WebhookPayload | None:
    """
    Safe version of analyze_payload that returns None instead of raising.

    Useful for quick validation without try/except blocks.
    """
    try:
        return WebhookPayload.model_validate(raw_payload)
    except ValidationError:
        return None


# ──────────────────────────────────────────────────────────────
# Helper functions for common extraction patterns
# ──────────────────────────────────────────────────────────────


def extract_text_messages(payload: WebhookPayload) -> list[tuple[str, str, str]]:
    """
    Extract all text messages as (sender_wa_id, message_body, timestamp) tuples.

    Returns:
        List of tuples: [(wa_id, body, timestamp), ...]
    """
    results: list[tuple[str, str, str]] = []
    for msg in payload.text_messages:
        body = msg.text.body if msg.text else ""
        results.append((msg.from_, body, msg.timestamp))
    return results


def extract_first_text(payload: WebhookPayload) -> tuple[str, str, str] | None:
    """
    Extract the first text message as (sender_wa_id, message_body, timestamp).

    Returns:
        Tuple or None if no text messages found.
    """
    texts = extract_text_messages(payload)
    return texts[0] if texts else None


def extract_voice_messages(payload: WebhookPayload) -> list[dict[str, Any]]:
    """
    Extract voice message metadata for processing.

    Returns:
        List of dicts with: from_, media_id, mime_type, url, timestamp
    """
    results: list[dict[str, Any]] = []
    for msg in payload.voice_messages:
        if msg.audio:
            results.append(
                {
                    "from": msg.from_,
                    "media_id": msg.audio.id,
                    "mime_type": msg.audio.mime_type,
                    "url": msg.audio.url,
                    "sha256": msg.audio.sha256,
                    "timestamp": msg.timestamp,
                }
            )
    return results


def get_message_summary(payload: WebhookPayload) -> dict[str, Any]:
    """
    Generate a concise summary of the webhook payload for logging/debugging.
    """
    return {
        "object": payload.object,
        "business_phone_id": payload.business_phone_number_id,
        "total_messages": len(payload.all_messages),
        "text_count": len(payload.text_messages),
        "voice_count": len(payload.voice_messages),
        "contacts": [c.wa_id for c in (payload.entry[0].changes[0].value.contacts or []) if c.wa_id]
        if payload.entry
        else [],
    }
