"""
System prompt builder for AI responses.

🐍 PYTHON NATIVE: Clean string formatting with f-strings instead of template literals
"""

from __future__ import annotations

from typing import Any


def build_system_prompt(
    profile: dict[str, Any] | None,
    current_msg: str,
    is_group: bool = False,
) -> str:
    """
    Build the system prompt for Groq LLM.

    Args:
        profile: User profile dict (or None for new users)
        current_msg: The current user message
        is_group: Whether this is a group conversation

    Returns:
        Complete system prompt string
    """
    # Base Dominican persona prompt
    base_prompt = """Eres "Unknown", un asistente virtual dominicano con "tigueraje". Eres amigable, casual y hablas como un pana de verdad.

Reglas de Oro:
1. Respuestas CORTAS (1-2 líneas máximo).
2. Usa modismos dominicanos naturales (pana, klk, vaina, tigueraje).
3. NO expliques tus capacidades técnicas. Solo actúa.
4. MÁXIMO 1 emoji por mensaje.

🎬 PROTOCOLO DE VIDEO (CRÍTICO):
Si el usuario pide un video, meme, risa o contenido visual, DEBES incluir la etiqueta <send vid> en tu respuesta.
- El sistema detectará esta etiqueta y enviará el video automáticamente.
- Si el usuario proporciona un link específico, úsalo así: <send vid https://link.com/video.mp4>
- Si NO proporcionas link, el sistema usará un video por defecto.
- Ejemplo Usuario: "Mándame un video"
- Tu Respuesta: "Toma esto pana <send vid>"

⏳ PROTOCOLO DE RETRASO (SUSPENSE):
Si quieres generar suspense, usa <send video delayed>.
- El sistema enviará el video 30-60 segundos después.
- No le digas al usuario que hay retraso. Solo di "Aguanta un toque..." o "Dame un segundito...".

💬 CITAS Y RESPUESTAS:
- Usa <contextual reply> si necesitas citar el mensaje anterior para aclarar algo.
- Usa <message X minutes> para programar recordatorios.

IMPORTANTE:
- Las etiquetas (<send vid>, etc.) se borran antes de mostrar el texto al usuario.
- NO menciones las etiquetas en tu texto visible.
- Si el usuario dice "klk" o saluda, responde normal.
- Si el usuario dice "video", "meme", "risa", "manda algo", USA <send vid>.

Link por defecto si no se especifica: https://slide-avoid-ages-volvo.trycloudflare.com/static/videos/long2.mp4
"""

    # Add group-aware context if applicable
    if is_group:
        base_prompt += "\n\nContexto: Chat grupal. Sé breve y no asumas contexto personal."

    # Add natural name request for new users
    if profile is None:
        base_prompt += "\n\nNota: Usuario nuevo. Puedes preguntar su nombre casualmente si fluye, pero no insistas."

    # Add profile context if available
    if profile is not None:
        context_parts = []

        if profile.get("name"):
            context_parts.append(f"Nombre: {profile['name']}")

        if profile.get("traits"):
            traits = profile["traits"]
            if isinstance(traits, dict) and traits:
                traits_str = ", ".join(f"{k}: {v}" for k, v in list(traits.items())[:5])
                context_parts.append(f"Características: {traits_str}")

        if profile.get("topics"):
            topics = profile["topics"]
            if isinstance(topics, list) and topics:
                topics_str = ", ".join(topics[:5])
                context_parts.append(f"Temas de interés: {topics_str}")

        if profile.get("notes"):
            notes = profile["notes"]
            context_parts.append(
                f"Notas: {notes[:100]}..." if len(notes) > 100 else f"Notas: {notes}"
            )

        if context_parts:
            base_prompt += "\n\nContexto del usuario:\n" + "\n".join(context_parts)

    # Add conversation history context hint
    base_prompt += (
        f'\n\nMensaje actual del usuario: "{current_msg[:500]}"'
        if len(current_msg) > 500
        else f'\n\nMensaje actual del usuario: "{current_msg}"'
    )

    return base_prompt


def extract_name_from_message(message: str) -> str | None:
    """
    Attempt to extract a name from a user message.
    """
    import re

    patterns = [
        r"(?:me llamo|yo soy|soy)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"(?:mi nombre es)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"([A-Z][a-z]+),\s*(?:mucho gusto|encantado|encantada)",
    ]

    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


def update_profile_with_context(
    profile: dict[str, Any] | None,
    user_message: str,
    ai_response: str,
) -> dict[str, Any] | None:
    """
    Extract potential profile updates from conversation.
    """
    if profile is None:
        profile = {}

    updated = False

    if not profile.get("name"):
        extracted_name = extract_name_from_message(user_message)
        if extracted_name:
            profile["name"] = extracted_name
            updated = True

    return profile if updated else None
