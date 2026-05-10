"""
Marker extraction from AI responses using regex.

🐍 PYTHON NATIVE: Compiled regex patterns for performance, dataclass for structured results
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import re


@dataclass
class MarkerResult:
    """Result of marker extraction."""

    # Video markers
    send_video: bool = False
    video_url: str | None = None


    # 🎬 DELAYED VIDEO: New delayed video marker support
    send_delayed_video: bool = False
    delayed_video_url: str | None = None

    # Schedule markers
    schedule_delay_seconds: int | None = None
    scheduled_message: str | None = None

    # Cleaned text (markers removed)
    cleaned_text: str = ""


# Compiled regex patterns for performance
VIDEO_RE = re.compile(r"<send\s+vid(?:eo)?\s*(?:([^\s>]+))?>", re.IGNORECASE)
# 🎬 DELAYED VIDEO: New regex for delayed video scheduling (30-60 seconds)
DELAYED_VIDEO_RE = re.compile(r"<send\s+vid(?:eo)?\s+delayed\s*(?:([^\s>]+))?>", re.IGNORECASE)
SCHEDULE_RE = re.compile(
    r"<message\s+(\d+)\s+(second|seconds|minute|minutes|hour|hours|min|h|m|s|seg)>",
    re.IGNORECASE
)


def parse_time_unit(unit: str) -> int:
    """
    Convert time unit string to seconds.

    Args:
        unit: Time unit string (seconds, minutes, hours, etc.)

    Returns:
        Number of seconds
    """
    unit_lower = unit.lower()

    if unit_lower in ("second", "seconds", "s", "seg"):
        return 1
    elif unit_lower in ("minute", "minutes", "min", "m"):
        return 60
    elif unit_lower in ("hour", "hours", "h"):
        return 3600
    else:
        # Default to seconds if unknown
        return 1


def extract_markers(text: str) -> MarkerResult:
    """
    Extract all markers from AI response text.

    Args:
        text: Raw AI response text potentially containing markers

    Returns:
        MarkerResult with extracted data and cleaned text
    """
    result = MarkerResult(cleaned_text=text)

    # Extract video marker
    video_match = VIDEO_RE.search(text)
    if video_match:
        result.send_video = True
        url = video_match.group(1)
        if url:
            result.video_url = url.strip()
        # Remove the marker from cleaned text
        result.cleaned_text = VIDEO_RE.sub("", result.cleaned_text).strip()


    # 🎬 DELAYED VIDEO: Check for delayed video marker FIRST (more specific)
    delayed_video_match = DELAYED_VIDEO_RE.search(text)
    if delayed_video_match:
        result.send_delayed_video = True
        url = delayed_video_match.group(1)
        if url:
            result.delayed_video_url = url.strip()
        # Remove the marker from cleaned text
        result.cleaned_text = DELAYED_VIDEO_RE.sub("", result.cleaned_text).strip()

    # Extract regular video marker (only if not already a delayed video)
    if not result.send_delayed_video:
        video_match = VIDEO_RE.search(text)
        if video_match:
            result.send_video = True
            url = video_match.group(1)
            if url:
                result.video_url = url.strip()
            # Remove the marker from cleaned text
            result.cleaned_text = VIDEO_RE.sub("", result.cleaned_text).strip()

    # Extract schedule marker
    schedule_match = SCHEDULE_RE.search(text)
    if schedule_match:
        value = int(schedule_match.group(1))
        unit = schedule_match.group(2)
        seconds_multiplier = parse_time_unit(unit)
        result.schedule_delay_seconds = value * seconds_multiplier
        # Store the message that should be scheduled (text after marker or full response)
        # For now, we'll use a default acknowledgment
        result.scheduled_message = "¡Listo! Te envío un recordatorio."
        # Remove the marker from cleaned text
        result.cleaned_text = SCHEDULE_RE.sub("", result.cleaned_text).strip()

    # Clean up multiple whitespace that may result from marker removal
    result.cleaned_text = re.sub(r"\s+", " ", result.cleaned_text).strip()

    return result


def calculate_execute_at(delay_seconds: int) -> int:
    """
    Calculate Unix timestamp for task execution.

    Args:
        delay_seconds: Seconds from now when task should execute

    Returns:
        Unix timestamp (int)
    """
    execute_time = datetime.now(UTC) + timedelta(seconds=delay_seconds)
    return int(execute_time.timestamp())


def strip_all_markers(text: str) -> str:
    """
    Remove all markers from text without extracting them.

    Useful when you just want clean text.

    Args:
        text: Text potentially containing markers

    Returns:
        Cleaned text with all markers removed
    """
    cleaned = text
    cleaned = DELAYED_VIDEO_RE.sub("", cleaned)  # 🎬 DELAYED VIDEO: Strip delayed video markers
    cleaned = VIDEO_RE.sub("", cleaned)
    cleaned = SCHEDULE_RE.sub("", cleaned)
    # Clean up multiple whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def has_any_marker(text: str) -> bool:
    """
    Check if text contains any markers.

    Args:
        text: Text to check

    Returns:
        True if any marker found, False otherwise
    """
    return bool(DELAYED_VIDEO_RE.search(text) or VIDEO_RE.search(text) or SCHEDULE_RE.search(text))
