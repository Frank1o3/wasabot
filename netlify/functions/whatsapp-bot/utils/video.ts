// netlify/functions/whatsapp-bot/utils/video.ts

/**
 * Normalizes text: removes accents, lowercases, collapses whitespace
 */
const normalize = (text: string): string => {
	return text
		.toLowerCase()
		.normalize('NFD') // Decompose accented chars
		.replace(/[\u0300-\u036f]/g, '') // Remove diacritics
		.replace(/\s+/g, ' ')
		.trim();
};

export const wantsVideo = (text: string): boolean => {
	const t = normalize(text);
	const triggers = [
		'show me a vid',
		'show me a video',
		'send video',
		'send me a video',
		'manda un video',
		'mandame un video',
		'muéstrame un video',
		'pasame un video',
		'quiero un video',
		'envía un video',
		// Add flexible variants:
		'mandes un video',
		'mandar video',
		'manda video',
		'quiero ver video',
	];
	return triggers.some((trigger) => t.includes(normalize(trigger)));
};

export const SEND_VID_MARKER = /<send\s*vid>/i;

export const processVideoMarker = (reply: string): { cleaned: string; shouldSend: boolean } => {
	const shouldSend = SEND_VID_MARKER.test(reply);
	if (shouldSend) {
		const cleaned = reply
			.replace(SEND_VID_MARKER, '')
			.trim()
			.replace(/[\s,]+$/, '')
			.replace(/\s+([.!?])/g, '$1');
		return { cleaned, shouldSend: true };
	}
	return { cleaned: reply, shouldSend: false };
};
