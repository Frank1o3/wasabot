"""
Typing indicators and read receipt handlers for WhatsApp.

👤 HUMANITY FEATURE: Shows "typing..." status and marks messages as read for better UX
"""
from __future__ import annotations

import asyncio

import httpx

from wasabot.config import get_settings
from wasabot.services.logger import get_logger, get_correlation_id

logger = get_logger(__name__)


async def send_typing_indicator(
    phone_number_id: str,
    access_token: str,
    message_id: str,
) -> None:
    """
    👤 HUMANITY FEATURE: Send typing indicator to user.
    
    Fire-and-forget operation. Logs errors but never raises.
    Auto-dismisses after 25 seconds OR when a message is sent.
    
    Args:
        phone_number_id: WhatsApp Business Phone Number ID
        access_token: WhatsApp API access token
        message_id: Incoming message WAMID to reply to
    """
    correlation_id = get_correlation_id() or ""
    base_url = "https://graph.facebook.com/v21.0"
    endpoint = f"{phone_number_id}/messages"
    url = f"{base_url}/{endpoint}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
        "typing_indicator": {"type": "text"},
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(2):  # Max 2 attempts
            try:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    logger.info(
                        "typing_indicator_sent",
                        extra={"meta": {"correlation_id": correlation_id, "message_id": message_id}}
                    )
                    return
                
                # Rate limit - wait and retry once
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 1))
                    logger.warning(
                        f"typing_indicator_rate_limit | attempt={attempt + 1} | retry_after={retry_after}s",
                        extra={"meta": {"correlation_id": correlation_id}}
                    )
                    await asyncio.sleep(retry_after)
                    continue
                
                # Client error - don't retry
                if 400 <= response.status_code < 500:
                    logger.warning(
                        f"typing_indicator_client_error | status={response.status_code}",
                        extra={"meta": {"correlation_id": correlation_id}}
                    )
                    return
                
                # Server error - retry once
                if 500 <= response.status_code < 600:
                    logger.warning(
                        f"typing_indicator_server_error | status={response.status_code} | attempt={attempt + 1}",
                        extra={"meta": {"correlation_id": correlation_id}}
                    )
                    await asyncio.sleep(1)
                    continue
                    
            except httpx.TimeoutException as e:
                logger.warning(
                    f"typing_indicator_timeout | attempt={attempt + 1} | error={str(e)}",
                    extra={"meta": {"correlation_id": correlation_id}}
                )
                if attempt < 1:
                    await asyncio.sleep(1)
                continue
                
            except httpx.RequestError as e:
                logger.error(
                    f"typing_indicator_request_error | error={str(e)}",
                    extra={"meta": {"correlation_id": correlation_id}}
                )
                return
    
    # All retries exhausted
    logger.warning(
        "typing_indicator_all_retries_failed",
        extra={"meta": {"correlation_id": correlation_id, "message_id": message_id}}
    )


async def mark_message_read(
    phone_number_id: str,
    access_token: str,
    message_id: str,
) -> None:
    """
    👤 HUMANITY FEATURE: Mark incoming message as read.
    
    Fire-and-forget operation. Never raises exceptions.
    Should be called immediately after receiving a message.
    
    Args:
        phone_number_id: WhatsApp Business Phone Number ID
        access_token: WhatsApp API access token
        message_id: Incoming message WAMID to mark as read
    """
    correlation_id = get_correlation_id() or ""
    base_url = "https://graph.facebook.com/v21.0"
    endpoint = f"{phone_number_id}/messages"
    url = f"{base_url}/{endpoint}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(2):  # Max 2 attempts
            try:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    logger.info(
                        "message_marked_read",
                        extra={"meta": {"correlation_id": correlation_id, "message_id": message_id}}
                    )
                    return
                
                # Rate limit - wait and retry once
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 1))
                    logger.warning(
                        f"mark_read_rate_limit | attempt={attempt + 1} | retry_after={retry_after}s",
                        extra={"meta": {"correlation_id": correlation_id}}
                    )
                    await asyncio.sleep(retry_after)
                    continue
                
                # Client error - log and return
                if 400 <= response.status_code < 500:
                    logger.warning(
                        f"mark_read_client_error | status={response.status_code}",
                        extra={"meta": {"correlation_id": correlation_id}}
                    )
                    return
                
                # Server error - retry once
                if 500 <= response.status_code < 600:
                    logger.warning(
                        f"mark_read_server_error | status={response.status_code} | attempt={attempt + 1}",
                        extra={"meta": {"correlation_id": correlation_id}}
                    )
                    await asyncio.sleep(1)
                    continue
                    
            except httpx.TimeoutException as e:
                logger.warning(
                    f"mark_read_timeout | attempt={attempt + 1} | error={str(e)}",
                    extra={"meta": {"correlation_id": correlation_id}}
                )
                if attempt < 1:
                    await asyncio.sleep(1)
                continue
                
            except httpx.RequestError as e:
                logger.error(
                    f"mark_read_request_error | error={str(e)}",
                    extra={"meta": {"correlation_id": correlation_id}}
                )
                return
    
    # All retries exhausted
    logger.warning(
        "mark_read_all_retries_failed",
        extra={"meta": {"correlation_id": correlation_id, "message_id": message_id}}
    )
