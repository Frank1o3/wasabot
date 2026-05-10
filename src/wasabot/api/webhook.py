# src/wasabot/webhook.py
import os
from pathlib import Path
import secrets

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from wasabot.analyzer import analyze_payload_safe, get_message_summary

router = APIRouter(prefix="/webhook", tags=["webhook"])
temp_file = Path(__file__).parent / "data.json"


@router.get("/")
async def webhook_get(request: Request) -> PlainTextResponse:
    """
    WhatsApp/Meta webhook verification endpoint.
    Handles GET requests with hub.mode, hub.challenge, hub.verify_token params.
    """
    params = dict(request.query_params)
    mode = params.get("hub.mode") or params.get("hub_mode")
    challenge = params.get("hub.challenge") or params.get("hub_challenge")
    verify_token = params.get("hub.verify_token") or params.get("hub_verify_token")

    wa_verify_token = os.getenv("WA_VERIFY_TOKEN")

    # Validate required params
    if not mode or not challenge or not verify_token:
        print("[WEBHOOK] ❌ missing required verification params")
        return PlainTextResponse(content="Missing parameters", status_code=400)

    # Only "subscribe" is valid for verification
    if mode != "subscribe":
        print(f"[WEBHOOK] ⚠️ invalid mode: {mode}")
        return PlainTextResponse(content="Invalid mode", status_code=400)

    # Constant-time token comparison (prevents timing attacks)
    if wa_verify_token and secrets.compare_digest(verify_token, wa_verify_token):
        print("[WEBHOOK] ✅ webhook_verified_success")
        return PlainTextResponse(content=challenge, status_code=200)

    # Failed verification - minimal logging in prod
    if os.getenv("ENVIRONMENT", "production") == "development":
        print(
            f"[WEBHOOK] ⚠️ verification_failed | "
            f"received={(verify_token or '')[:4]}... | "
            f"expected={(wa_verify_token or '')[:4]}..."
        )
    else:
        print("[WEBHOOK] ⚠️ verification_failed")

    return PlainTextResponse(content="Verification failed", status_code=403)


@router.post("/")
async def webhook_post(request: Request) -> PlainTextResponse:
    raw_payload = await request.json()

    # Parse with analyzer for typed access
    payload = analyze_payload_safe(raw_payload)

    if payload is None:
        print("[WEBHOOK] ❌ failed to parse payload")
        return PlainTextResponse(content="Invalid payload", status_code=400)

    # Now you have full IDE completion on `payload`! 🎉
    summary = get_message_summary(payload)
    print(f"[WEBHOOK] ✅ parsed | {summary}")

    # Example: Process text messages with autocompletion
    for msg in payload.text_messages:
        user_id = msg.from_  # ← IDE knows this is str
        body = msg.text.body if msg.text else ""  # ← IDE knows text is TextContent | None
        print(f"💬 [TEXT] from={user_id} | body='{body}'")

        # Access optional context/referral with completion
        if msg.context and msg.context.forwarded:
            print("   ↳ forwarded message")
        if msg.referral and msg.referral.source_type:
            print(f"   ↳ from ad: {msg.referral.source_type}")

    # Example: Process voice messages
    for msg in payload.voice_messages:
        if msg.audio:
            print(f"🎤 [VOICE] from={msg.from_} | media_id={msg.audio.id} | url={msg.audio.url}")

    # Save raw for debugging (optional)
    temp_file.write_text(str(raw_payload))

    return PlainTextResponse(content="Event received", status_code=200)
