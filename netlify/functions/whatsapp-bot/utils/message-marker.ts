// netlify/functions/whatsapp-bot/utils/message-marker.ts

/**
 * Normalizes text for reliable regex matching:
 * - Lowercases
 * - Removes accents/diacritics
 * - Collapses multiple spaces to single space
 * - Removes zero-width chars and other invisible Unicode
 */
const normalizeForMatching = (text: string): string => {
	return text
		.toLowerCase()
		.normalize('NFD') // Decompose accented chars
		.replace(/[\u0300-\u036f]/g, '') // Remove diacritics (é → e)
		.replace(/[\u200B-\u200D\uFEFF]/g, '') // Remove zero-width chars
		.replace(/\s+/g, ' ') // Collapse whitespace
		.trim();
};

/**
 * Regex to detect <message X timeunit> marker
 * - Normalized text input avoids accent/emoji issues
 * - Includes ALL common English/Spanish time units
 */
export const MESSAGE_MARKER_REGEX =
	/<\s*message\s+(\d+)\s+(segundo|seg|segundos|secs|min|minuto|minutos|minute|minutes|hora|horas|hour|hours|día|días|day|days|week|weeks)\s*>/i;

/**
 * Checks if reply contains marker and returns cleaned text + parsed delay
 */
export const processMessageMarker = (
	reply: string,
): {
	cleaned: string;
	shouldSchedule: boolean;
	delayMs: number | null;
	timeString: string | null;
} => {
	// Normalize for reliable matching (doesn't change original reply for sending)
	const normalized = normalizeForMatching(reply);
	const match = normalized.match(MESSAGE_MARKER_REGEX);

	if (match && match[1] && match[2]) {
		const amount = parseInt(match[1], 10);
		const unitRaw = match[2].toLowerCase();

		// Map all variants to canonical units for ms calculation
		const unitMap: Record<string, { ms: number; display: string }> = {
			segundo: { ms: 1000, display: 'segundo' },
			segundos: { ms: 1000, display: 'segundo' },
			seg: { ms: 1000, display: 'segundo' },
			secs: { ms: 1000, display: 'segundo' },
			minuto: { ms: 60000, display: 'minuto' },
			minutos: { ms: 60000, display: 'minuto' },
			min: { ms: 60000, display: 'minuto' },
			minute: { ms: 60000, display: 'minuto' },
			minutes: { ms: 60000, display: 'minuto' },
			hora: { ms: 3600000, display: 'hora' },
			horas: { ms: 3600000, display: 'hora' },
			hour: { ms: 3600000, display: 'hora' },
			hours: { ms: 3600000, display: 'hora' },
			día: { ms: 86400000, display: 'día' },
			días: { ms: 86400000, display: 'día' },
			day: { ms: 86400000, display: 'día' },
			days: { ms: 86400000, display: 'día' },
			week: { ms: 604800000, display: 'semana' },
			weeks: { ms: 604800000, display: 'semana' },
		};

		const unitData = unitMap[unitRaw];
		if (!unitData) {
			console.warn(`⚠️ Unknown time unit: "${unitRaw}"`);
			return { cleaned: reply, shouldSchedule: false, delayMs: null, timeString: null };
		}

		const delayMs = unitData.ms * amount;
		const timeString = `${amount} ${unitData.display}`;

		// Remove marker from ORIGINAL reply (not normalized) to preserve emojis/formatting
		const cleaned = reply
			.replace(MESSAGE_MARKER_REGEX, '')
			.trim()
			.replace(/[\s,]+$/, '')
			.replace(/\s+([.!?])/g, '$1');

		console.log(
			`⏰ Marker DETECTED: "${match[0]}" | Unit: "${unitRaw}" → ${timeString} | Cleaned: "${cleaned.slice(0, 80)}..."`,
		);
		return { cleaned, shouldSchedule: true, delayMs, timeString };
	}

	// Debug: log why it didn't match (helpful for troubleshooting)
	if (/<\s*message/i.test(normalizeForMatching(reply))) {
		console.log(`⚠️ Marker-like text found but full regex didn't match.`);
		console.log(`   Normalized snippet: "${normalizeForMatching(reply).slice(0, 120)}"`);
		console.log(`   Original snippet: "${reply.slice(0, 120)}"`);
	}

	return { cleaned: reply, shouldSchedule: false, delayMs: null, timeString: null };
};
