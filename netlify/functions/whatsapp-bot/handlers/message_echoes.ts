// netlify/functions/whatsapp-bot/handlers/message_echoes.ts

import type { WhatsAppWebhookBody, HandlerResponse } from '../types';
import { createLogger } from '../utils/logger';

/**
 * Handles 'message_echoes' events (messages sent by the bot that are echoed back)
 * Currently logs them for analytics; can be extended for delivery tracking
 */
export const handleMessageEchoes = async (
	body: WhatsAppWebhookBody,
	context?: { correlationId: string },
): Promise<HandlerResponse> => {
	const logger = createLogger(context?.correlationId || 'no-correlation-id');

	try {
		const echoes = body.entry?.[0]?.changes?.[0]?.value?.messages || [];

		for (const echo of echoes) {
			logger.info('message_echo', {
				messageId: echo.id,
				to: echo.from, // In echoes, 'from' is the recipient
				type: echo.type,
			});
			// Future: Update message status in database, track delivery, etc.
		}

		return { statusCode: 200, body: 'OK' };
	} catch (error) {
		logger.error('handleMessageEchoes_error', { errorMessage: (error as Error).message });
		return { statusCode: 500, body: 'Error' };
	}
};
