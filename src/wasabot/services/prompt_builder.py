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
    base_prompt = """Eres un asistente virtual dominicano, amigable y casual. Responde de forma corta y natural, como en una conversación real de WhatsApp.

Reglas importantes:
1. Respuestas MÁXIMO 2-3 líneas, preferiblemente 1 línea
2. Usa lenguaje coloquial dominicano cuando sea apropiado
3. Sé útil pero mantén el tono conversacional
4. NO uses emojis excesivos (máximo 1 por mensaje)
5. Si no sabes algo, admítelo naturalmente

Marcadores especiales que puedes usar:
- <send vid> o <send video> - Para enviar un video (solo si es relevante)
- <send video URL> - Para enviar un video específico con URL
- <message X unit> - Para programar un mensaje futuro (X = número, unit = seconds/minutes/hours)

Ejemplos de marcadores:
- "Aquí tienes lo que pediste <send vid>"
- "Te recuerdo en 5 minutos <message 5 minutes>"
- "Dame un segundo <send video https://example.com/video.mp4>"

IMPORTANTE: Los marcadores se eliminan automáticamente antes de enviar. Úsalos solo cuando tenga sentido."""

    # Add group-aware context if applicable
    if is_group:
        base_prompt += "\n\nContexto: Este es un chat grupal. Mantén respuestas breves y relevantes para el grupo. No asumas que todos conocen el contexto personal."

    # Add natural name request for new users
    if profile is None:
        base_prompt += "\n\nNota: Este es un usuario nuevo. Si la conversación fluye naturalmente, puedes preguntar su nombre de forma casual, pero NO insistas."

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
            context_parts.append(f"Notas: {profile['notes'][:100]}...") if len(profile.get("notes", "")) > 100 else context_parts.append(f"Notas: {profile['notes']}")
        
        if context_parts:
            base_prompt += "\n\nContexto del usuario:\n" + "\n".join(context_parts)

    # Add conversation history context hint
    base_prompt += f"\n\nMensaje actual del usuario: \"{current_msg[:500]}\"" if len(current_msg) > 500 else f"\n\nMensaje actual del usuario: \"{current_msg}\""

    return base_prompt


def extract_name_from_message(message: str) -> str | None:
    """
    Attempt to extract a name from a user message.
    
    🐍 PYTHON NATIVE: Simple regex-based extraction instead of complex parsing
    """
    import re
    
    # Pattern: "me llamo X", "soy X", "mi nombre es X"
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
    
    Returns updated profile dict or None if no changes.
    """
    if profile is None:
        profile = {}
    
    updated = False
    
    # Try to extract name if not present
    if not profile.get("name"):
        extracted_name = extract_name_from_message(user_message)
        if extracted_name:
            profile["name"] = extracted_name
            updated = True
    
    # Could add more extraction logic here (topics, traits, etc.)
    
    return profile if updated else None
