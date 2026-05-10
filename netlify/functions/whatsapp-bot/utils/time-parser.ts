// netlify/functions/whatsapp-bot/utils/time-parser.ts

/**
 * Parses natural language time expressions into milliseconds
 * Supports Spanish & English variants
 */
export const parseTimeExpression = (text: string): number | null => {
	const t = text
		.toLowerCase()
		.normalize('NFD')
		.replace(/[\u0300-\u036f]/g, '');

	// Extract number and unit
	const match = t.match(
		/(?:en|dentro de|dentro|pasados?|después de|in|within|after)?\s*(\d+)\s*(segundo|seg|min|minuto|hora|horas|día|días|day|days|week|weeks)/i,
	);
	if (!match || !match[1] || !match[2]) return null;

	const amount = parseInt(match[1], 10);
	const unit = match[2].toLowerCase();

	const multipliers: Record<string, number> = {
		segundo: 1000,
		seg: 1000,
		minuto: 60000,
		min: 60000,
		hora: 3600000,
		horas: 3600000,
		día: 86400000,
		días: 86400000,
		day: 86400000,
		days: 86400000,
		week: 604800000,
		weeks: 604800000,
	};

	const ms = multipliers[unit] * amount;
	// Cap at 7 days to avoid abuse
	return ms <= 7 * 86400000 ? ms : null;
};

/**
 * Formats milliseconds into human-readable Spanish
 */
export const formatTimeSpanish = (ms: number): string => {
	const minutes = Math.round(ms / 60000);
	const hours = Math.round(ms / 3600000);
	const days = Math.round(ms / 86400000);

	if (days >= 1) return `${days} día${days > 1 ? 's' : ''}`;
	if (hours >= 1) return `${hours} hora${hours > 1 ? 's' : ''}`;
	return `${minutes} minuto${minutes > 1 ? 's' : ''}`;
};
