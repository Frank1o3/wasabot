// netlify/functions/whatsapp-bot/handlers/standby.ts

import type { WhatsAppWebhookBody, HandlerResponse } from '../types';
import { createLogger } from '../utils/logger';

/**
 * Handles 'standby' events (messages received when the user is in standby mode)
 * Currently logs them; can be extended for queueing or priority handling
 */
export const handleStandby = async (
	body: WhatsAppWebhookBody,
	context?: { correlationId: string },
): Promise<HandlerResponse> => {
	const logger = createLogger(context?.correlationId || 'no-correlation-id');

	try {
		const standbyMessages = body.entry?.[0]?.changes?.[0]?.value?.messages ?? [];

		for (const msg of standbyMessages) {
			logger.info('standby_message', {
				messageId: msg.id,
				from: msg.from,
				type: msg.type,
				text: msg.text?.body?.slice(0, 100),
			});
			// Future: Queue for later processing, send auto-reply, etc.
		}

		return { statusCode: 200, body: 'OK' };
	} catch (error) {
		logger.error('handleStandby_error', { errorMessage: (error as Error).message });
		return { statusCode: 500, body: 'Error' };
	}
};
