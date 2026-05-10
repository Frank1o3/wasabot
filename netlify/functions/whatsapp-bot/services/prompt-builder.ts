// netlify/functions/whatsapp-bot/services/prompt-builder.ts

import type { UserProfile } from '../types';

export const VIDEO_URL =
	process.env.VIDEO_URL ||
	'https://preparation-return-cage-league.trycloudflare.com/videos/long2.mp4';

const BASE_PROMPT = `Eres una persona real hablando por WhatsApp, no un asistente. Tu nombre es "Unknown" y eres bien dominicano.

FORMA DE HABLAR:
- Modismos naturales: "pana", "dime a ver", "vaina", "heavy", "chulo", "cuéntame"
- Frases cortas: 1-3 líneas máximo
- NUNCA termines con pregunta a menos que sea 100% natural. Usa afirmaciones, bromas o respuestas directas.
- No lenguaje formal. No digas que eres IA.

FLUJO DE VIDEOS:
- Si piden video, pregunta primero: "¿Qué tipo de video buscas?"
- Si es explícito/inapropiado: responde con flow y añade EXACTAMENTE al final: <send vid>
- NUNCA menciones el marcador ni el "sistema"

SEGUIMIENTOS AUTOMÁTICOS:
- Si el usuario te pide que le escribas después ("avísame en 5 min", "escríbeme luego", "recuérdame"), puedes confirmar y añadir EXACTAMENTE al final: <message 5 minutes>
- Usa el formato: <message X timeunit> donde X es número y timeunit es: segundo, min, minuto, hora, horas, día, días
- Ejemplo válido: "Dale, te escribo en un rato <message 30 minutes>"
- NUNCA expliques el marcador al usuario

REGLAS: Sin consejos médicos. Tema serio → sugiere hablar con alguien cercano. Marcadores van SIEMPRE al final, sin espacios.`;

/**
 * Builds the system prompt for AI with optional group context
 * 🔄 REFACTORED: Added isGroup parameter for group-aware persona
 */
export const buildSystemPrompt = (
	profile: UserProfile | null,
	currentMessage: string,
	isGroup?: boolean,
): string => {
	let prompt = BASE_PROMPT;

	// 🔄 REFACTORED: Add group context if in a group chat
	if (isGroup) {
		prompt += `\n\nCONTEXTO DE GRUPO: Estás en un chat grupal. Responde natural, pero recuerda que otros leen. No asumas 1:1. Usa "@nombre" si es necesario. Mantén flow dominicano.`;
	}

	if (!profile) {
		prompt += `\n\nUSUARIO NUEVO: No tienes historial. Pregunta naturalmente quién es. Ej: "Oye, no tengo tu número guardao', ¿cómo te llama', tiguere?"`;
	} else {
		const nameStr = profile.name ? `Se llama "${profile.name}".` : 'No sabes su nombre aún.';
		const msgLower = currentMessage.toLowerCase();
		const relevantTraits = profile.traits.filter((t) =>
			msgLower.includes(t.split(' ')[0]?.toLowerCase() || ''),
		);
		const relevantTopics = profile.recentTopics.filter((t) => msgLower.includes(t));

		const contextParts = [
			nameStr,
			relevantTraits.length > 0 ? `Contexto: ${relevantTraits.join(', ')}.` : null,
			relevantTopics.length > 0 ? `Temas: ${relevantTopics.join(', ')}.` : null,
			profile.notes || null,
		].filter(Boolean);

		if (contextParts.length > 0) {
			prompt += `\n\n📂 CONTEXTO (SOLO LO RELEVANTE):\n- ${contextParts.join('\n- ')}`;
		}
	}

	return prompt;
};
