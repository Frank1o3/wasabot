import { sendWaMessage } from './whatsapp';
import { info, warn } from '../utils/logger';

// 🔄 REFACTORED: Typing indicator configuration
const TYPING_SPEED_CHARS_PER_SEC = 25; // Realistic reading/typing speed
const MAX_TYPING_DELAY_MS = 18000; // Safety cap (under 25s auto-dismiss)
const HARD_CAP_DELAY_MS = 15000; // Hard cap to ensure Netlify timeout safety

/**
 * Sends the official typing indicator to WhatsApp Cloud API.
 * Fire-and-forget: Errors are logged but not thrown to avoid breaking the main flow.
 */
export async function sendTypingIndicator(
	phoneNumberId: string,
	accessToken: string,
	incomingMessageId: string,
	correlationId: string,
): Promise<void> {
	const url = `https://graph.facebook.com/v25.0/${phoneNumberId}/messages`;

	const payload = {
		messaging_product: 'whatsapp',
		status: 'read', // Required base status
		message_id: incomingMessageId,
		typing_indicator: {
			type: 'text',
		},
	};

	try {
		const response = await fetch(url, {
			method: 'POST',
			headers: {
				Authorization: `Bearer ${accessToken}`,
				'Content-Type': 'application/json',
			},
			body: JSON.stringify(payload),
		});

		if (!response.ok) {
			const errorText = await response.text();
			warn('typing_indicator_failed', correlationId, {
				status: response.status,
				error: errorText,
				details: 'Non-critical UX enhancement failure',
			});
		} else {
			info('typing_indicator_sent', correlationId, { messageId: incomingMessageId });
		}
	} catch (error) {
		warn('typing_indicator_error', correlationId, {
			error: error instanceof Error ? error.message : 'Unknown error',
			details: 'Network or system error sending typing indicator',
		});
	}
}

/**
 * Calculates a realistic typing delay based on text length.
 * Adds ±10% jitter to feel human.
 */
export function calculateTypingDelay(text: string): number {
	const baseDelay = (text.length / TYPING_SPEED_CHARS_PER_SEC) * 1000;

	// Add ±10% jitter
	const jitter = (Math.random() - 0.5) * 0.2 * baseDelay;
	const calculatedDelay = baseDelay + jitter;

	// Safety cap to stay under WhatsApp's 25s auto-dismiss and Netlify timeouts
	if (calculatedDelay > MAX_TYPING_DELAY_MS) {
		return HARD_CAP_DELAY_MS;
	}

	// Minimum delay to ensure UI updates register (avoid instant flash)
	return Math.max(calculatedDelay, 800);
}

/**
 * Orchestrates the full typing flow:
 * 1. Calculate delay
 * 2. Fire typing indicator (non-blocking)
 * 3. Wait
 * 4. Send actual message
 */
export async function sendWithTypingFlow(
	to: string,
	text: string,
	incomingMessageId: string,
	correlationId: string,
): Promise<void> {
	const delayMs = calculateTypingDelay(text);

	info('typing_started', correlationId, {
		phone: to,
		delayMs,
		chars: text.length,
	});

	// Fire-and-forget typing indicator
	const phoneNumberId = process.env.WA_PHONE_NUMBER_ID;
	const accessToken = process.env.WA_ACCESS_TOKEN;

	if (phoneNumberId && accessToken) {
		sendTypingIndicator(phoneNumberId, accessToken, incomingMessageId, correlationId).catch(
			() => {
				/* Already logged internally */
			},
		);
	} else {
		warn('missing_env_vars', correlationId, {
			detail: 'Cannot send typing indicator without WA creds',
		});
	}

	// Wait for the calculated duration
	await new Promise((resolve) => setTimeout(resolve, delayMs));

	// Send the actual message
	await sendWaMessage(to, text, { correlationId });
}
