"""
WhatsApp Cloud API async client.

🐍 PYTHON NATIVE: httpx.AsyncClient for async HTTP, exponential backoff retries
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from wasabot.config import get_settings
from wasabot.services.logger import get_correlation_id, get_logger

logger = get_logger(__name__)


class WhatsAppAPIClient:
    """Async client for WhatsApp Cloud API."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._base_url = self._settings.whatsapp_base_url
        self._phone_number_id = self._settings.wa_phone_number_id
        self._access_token = self._settings.wa_access_token

    async def _get_headers(self) -> dict[str, str]:
        """Get authentication headers."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    async def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any] | None:
        """
        Make HTTP request with exponential backoff retry logic.
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            json_data: Optional JSON payload
            max_retries: Maximum retry attempts
        Returns:
            Response JSON dict or None on failure
        """
        url = f"{self._base_url}/{endpoint}"
        headers = await self._get_headers()
        correlation_id = get_correlation_id() or ""

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(max_retries):
                try:
                    if method.upper() == "POST":
                        response = await client.post(url, headers=headers, json=json_data)
                    else:
                        response = await client.get(url, headers=headers)

                    # Success
                    if response.status_code == 200:
                        return response.json()

                    # Rate limit - wait and retry
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 2**attempt))
                        logger.warning(
                            f"whatsapp_rate_limit | attempt={attempt + 1} | retry_after={retry_after}s",
                            extra={"meta": {"correlation_id": correlation_id}},
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    # Server error - retry with backoff
                    if 500 <= response.status_code < 600:
                        backoff = 2**attempt
                        logger.warning(
                            f"whatsapp_server_error | status={response.status_code} | attempt={attempt + 1}",
                            extra={"meta": {"correlation_id": correlation_id}},
                        )
                        await asyncio.sleep(backoff)
                        continue

                    # Client error - don't retry
                    logger.error(
                        f"whatsapp_client_error | status={response.status_code} | body={response.text[:200]}",
                        extra={"meta": {"correlation_id": correlation_id}},
                    )
                    return None

                except httpx.TimeoutException as e:
                    backoff = 2**attempt
                    logger.warning(
                        f"whatsapp_timeout | attempt={attempt + 1} | waiting={backoff}s",
                        extra={"meta": {"correlation_id": correlation_id, "exception": str(e)}},
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(backoff)
                    continue

                except httpx.RequestError as e:
                    logger.error(
                        f"whatsapp_request_error | error={e!s}",
                        extra={"meta": {"correlation_id": correlation_id}},
                    )
                    return None

            # All retries exhausted
            logger.error(
                f"whatsapp_all_retries_failed | endpoint={endpoint}",
                extra={"meta": {"correlation_id": correlation_id}},
            )
            return None

    async def send_text(
        self,
        wa_id: str,
        text: str,
        reply_to_message_id: str | None = None,
    ) -> bool:
        """
        Send a text message.
        Args:
            wa_id: Recipient WhatsApp ID
            text: Message text
            reply_to_message_id: Optional message ID to reply to (contextual reply)

        Returns:
            True if sent successfully, False otherwise
        """
        endpoint = f"{self._phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": wa_id,
            "type": "text",
            "text": {"body": text},
        }

        # 👤 HUMANITY FEATURE: Add contextual reply if message ID provided
        if reply_to_message_id:
            payload["context"] = {"message_id": reply_to_message_id}

        # 👤 HUMANITY FEATURE: Add contextual reply if message ID provided
        if reply_to_message_id:
            payload["context"] = {"message_id": reply_to_message_id}

        result = await self._request_with_retry("POST", endpoint, payload)

        if result:
            logger.info(f"whatsapp_text_sent | wa_id={wa_id}" + (f" | reply_to={reply_to_message_id}" if reply_to_message_id else ""))
            return True
        else:
            logger.error(f"whatsapp_text_failed | wa_id={wa_id}")
            return False

    async def send_video(
        self,
        wa_id: str,
        video_url: str,
        caption: str | None = None,
        reply_to_message_id: str | None = None,
    ) -> bool:
        """
        Send a video message.
        Args:
            wa_id: Recipient WhatsApp ID
            video_url: URL of the video to send
            caption: Optional caption text
            reply_to_message_id: Optional message ID to reply to (contextual reply)

        Returns:
            True if sent successfully, False otherwise
        """
        endpoint = f"{self._phone_number_id}/messages"
        payload: dict[str, str | dict[str, str]] = {
            "messaging_product": "whatsapp",
            "to": wa_id,
            "type": "video",
            "video": {
                "link": video_url,
            },
        }

        if caption:
            payload["video"]["caption"] = caption

        # 👤 HUMANITY FEATURE: Add contextual reply if message ID provided
        if reply_to_message_id:
            payload["context"] = {"message_id": reply_to_message_id}

        # 👤 HUMANITY FEATURE: Add contextual reply if message ID provided
        if reply_to_message_id:
            payload["context"] = {"message_id": reply_to_message_id}

        result = await self._request_with_retry("POST", endpoint, payload)

        if result:
            logger.info(f"whatsapp_video_sent | wa_id={wa_id} | url={video_url[:50]}..." + (f" | reply_to={reply_to_message_id}" if reply_to_message_id else ""))
            return True
        else:
            logger.error(f"whatsapp_video_failed | wa_id={wa_id}")
            return False

    async def download_media(self, media_url: str) -> bytes | None:
        """
        Download media file from WhatsApp.
        Args:
            media_url: Media download URL from webhook
        Returns:
            Raw bytes of media file or None on failure
        """
        headers = await self._get_headers()
        correlation_id = get_correlation_id() or ""

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.get(media_url, headers=headers)

                if response.status_code == 200:
                    logger.info(f"whatsapp_media_downloaded | url={media_url[:50]}...")
                    return response.content
                else:
                    logger.error(
                        f"whatsapp_media_download_failed | status={response.status_code}",
                        extra={"meta": {"correlation_id": correlation_id}},
                    )
                    return None

            except httpx.RequestError as e:
                logger.error(
                    f"whatsapp_media_download_error | error={e!s}",
                    extra={"meta": {"correlation_id": correlation_id}},
                )
                return None

    async def get_media_url(self, media_id: str) -> str | None:
        """
        Get downloadable URL for a media ID.
        Args:
            media_id: Media ID from webhook
        Returns:
            Download URL or None on failure
        """
        endpoint = f"{self._phone_number_id}/media/{media_id}"
        result = await self._request_with_retry("GET", endpoint)

        if result and "url" in result:
            return result["url"]
        return None


# Global client instance
_whatsapp_client: WhatsAppAPIClient | None = None


def get_whatsapp_client() -> WhatsAppAPIClient:
    """Get or create global WhatsApp API client."""
    global _whatsapp_client
    if _whatsapp_client is None:
        _whatsapp_client = WhatsAppAPIClient()
    return _whatsapp_client
