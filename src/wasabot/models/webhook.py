# src/wasabot/models/webhook.py
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Discriminator, Field, Tag

# ──────────────────────────────────────────────────────────────
# SHARED LEAF MODELS (reused across all message types)
# ──────────────────────────────────────────────────────────────


class ContactProfile(BaseModel):
    name: str | None = None


class Contact(BaseModel):
    profile: ContactProfile | None = None
    wa_id: str | None = None
    identity_key_hash: str | None = None


class Metadata(BaseModel):
    display_phone_number: str | None = None
    phone_number_id: str | None = None


class WelcomeMessage(BaseModel):
    text: str | None = None


class Referral(BaseModel):
    """Shared referral model for messages originating from Click-to-WhatsApp ads."""

    source_url: str | None = None
    source_id: str | None = None
    source_type: Literal["ad", "status_ad"] | None = None
    body: str | None = None
    headline: str | None = None
    media_type: str | None = None
    image_url: str | None = None
    video_url: str | None = None
    thumbnail_url: str | None = None
    ctwa_clid: str | None = None  # Omitted for Status ad placements
    welcome_message: WelcomeMessage | None = None


class ReferredProduct(BaseModel):
    catalog_id: str | None = None
    product_retailer_id: str | None = None


class MessageContext(BaseModel):
    """Shared context for forwarded messages or business-reply context."""

    from_: str | None = Field(None, alias="from")
    id: str | None = None
    referred_product: ReferredProduct | None = None
    forwarded: bool | None = None
    frequently_forwarded: bool | None = None


# ──────────────────────────────────────────────────────────────
# MESSAGE CONTENT MODELS (type-specific payloads)
# ──────────────────────────────────────────────────────────────


class TextContent(BaseModel):
    body: str


class AudioContent(BaseModel):
    """Used for both voice notes and generic audio files."""

    mime_type: str
    sha256: str
    id: str
    url: str | None = None  # Only present if media is hosted
    voice: bool | None = None  # True = voice note, False/None = audio file


# ──────────────────────────────────────────────────────────────
# 🚀 FUTURE CAPABILITY: New message type models (stubs)
# ──────────────────────────────────────────────────────────────


class StickerContent(BaseModel):
    """🚀 FUTURE CAPABILITY: Sticker message content."""

    mime_type: str  # "image/webp"
    sha256: str
    id: str
    url: str | None = None
    animated: bool | None = None


class ReactionContent(BaseModel):
    """🚀 FUTURE CAPABILITY: Reaction message content."""

    message_id: str  # ID of message being reacted to
    emoji: str | None = None  # Unicode emoji, None if reaction removed


class EditContent(BaseModel):
    """🚀 FUTURE CAPABILITY: Edited message content."""

    original_message_id: str
    message: dict[str, Any]  # Full edited message payload


class StickerMessageContent(BaseModel):
    """🚀 FUTURE CAPABILITY: Sticker message wrapper."""

    type: Literal["sticker"]
    sticker: StickerContent
    referral: Referral | None = None


class ReactionMessageContent(BaseModel):
    """🚀 FUTURE CAPABILITY: Reaction message wrapper."""

    type: Literal["reaction"]
    reaction: ReactionContent


class EditMessageContent(BaseModel):
    """🚀 FUTURE CAPABILITY: Edit message wrapper."""

    type: Literal["edit"]
    edit: EditContent


# ──────────────────────────────────────────────────────────────
# DISCRIMINATOR FUNCTION (FIXED: proper type hints)
# ──────────────────────────────────────────────────────────────


def message_type_discriminator(v: dict[str, Any]) -> str:
    """Extract the message type for Pydantic's discriminated union."""
    msg_type = v.get("type")
    return msg_type if isinstance(msg_type, str) else "unknown"


class TextMessageContent(BaseModel):
    type: Literal["text"]
    text: TextContent
    context: MessageContext | None = None
    referral: Referral | None = None


class AudioMessageContent(BaseModel):
    type: Literal["audio"]
    audio: AudioContent
    referral: Referral | None = None


class GroupTextMessageContent(BaseModel):
    """Text message sent in a group chat (has group_id at message level)."""

    type: Literal["text"]
    text: TextContent


# The actual discriminated union type
MessageContent = Annotated[
    Annotated[TextMessageContent, Tag("text")]
    | Annotated[AudioMessageContent, Tag("audio")]
    | Annotated[GroupTextMessageContent, Tag("group_text")],
    Discriminator(message_type_discriminator),
]


# ──────────────────────────────────────────────────────────────
# CORE MESSAGE MODEL (all common fields + type-specific content)
# ──────────────────────────────────────────────────────────────


class Message(BaseModel):
    """
    Unified message model. Common fields are at the top,
    type-specific content is in the 'content' field via discriminated union.
    """

    from_: str = Field(..., alias="from")
    id: str
    timestamp: str
    type: Literal[
        "text",
        "audio",
        "image",
        "video",
        "document",
        "location",
        "contacts",
        "interactive",
        "button",
        "template",
        "reaction",
        "sticker",
        "order",
        "system",
        "unknown",
    ]

    # Group-specific field (only present for group messages)
    group_id: str | None = None

    # Type-specific payload fields (flat for easier access)
    text: TextContent | None = None
    audio: AudioContent | None = None
    # 🚀 FUTURE CAPABILITY: Fields for new message types
    sticker: StickerContent | None = None
    reaction: ReactionContent | None = None
    edit: EditContent | None = None
    context: MessageContext | None = None
    referral: Referral | None = None

    # ─── Helper properties (FIXED: explicit bool returns) ───
    @property
    def is_text(self) -> bool:
        return self.type == "text" and self.text is not None

    @property
    def is_voice(self) -> bool:
        if self.type != "audio" or self.audio is None:
            return False
        return self.audio.voice is True

    @property
    def is_audio(self) -> bool:
        if self.type != "audio" or self.audio is None:
            return False
        return self.audio.voice is not True

    @property
    def is_group_message(self) -> bool:
        return self.group_id is not None

    # 🚀 FUTURE CAPABILITY: Helper properties for new message types
    @property
    def is_sticker(self) -> bool:
        """Check if this is a sticker message."""
        return self.type == "sticker" and self.sticker is not None

    @property
    def is_reaction(self) -> bool:
        """Check if this is a reaction message."""
        return self.type == "reaction" and self.reaction is not None

    @property
    def is_edit(self) -> bool:
        """Check if this is an edited message."""
        return self.type == "edit" and self.edit is not None


# ──────────────────────────────────────────────────────────────
# WEBHOOK PAYLOAD STRUCTURE
# ──────────────────────────────────────────────────────────────


class ChangeValue(BaseModel):
    messaging_product: Literal["whatsapp"]
    metadata: Metadata
    contacts: list[Contact] | None = None
    messages: list[Message] | None = None


class Change(BaseModel):
    value: ChangeValue
    field: Literal["messages"]


class Entry(BaseModel):
    id: str  # WhatsApp Business Account ID
    changes: list[Change]


class WebhookPayload(BaseModel):
    """
    Primary model for ALL WhatsApp Business webhook payloads.
    Use: WebhookPayload.model_validate(request_json)
    """

    object: Literal["whatsapp_business_account"]
    entry: list[Entry]

    # ─── Helper properties for easy access ───
    @property
    def all_messages(self) -> list[Message]:
        """Flatten all messages from all entries/changes."""
        messages: list[Message] = []
        for entry in self.entry:
            for change in entry.changes:
                if change.value.messages:
                    messages.extend(change.value.messages)
        return messages

    @property
    def text_messages(self) -> list[Message]:
        """Filter to only text-type messages."""
        return [m for m in self.all_messages if m.is_text]

    @property
    def voice_messages(self) -> list[Message]:
        """Filter to only voice note messages."""
        return [m for m in self.all_messages if m.is_voice]

    @property
    def first_message(self) -> Message | None:
        """Get the first message in the payload, if any."""
        msgs = self.all_messages
        return msgs[0] if msgs else None

    @property
    def business_phone_number_id(self) -> str | None:
        """Convenience accessor for the business phone number ID."""
        if self.entry and self.entry[0].changes:
            return self.entry[0].changes[0].value.metadata.phone_number_id
        return None
