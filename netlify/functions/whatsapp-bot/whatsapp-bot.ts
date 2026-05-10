// netlify/functions/whatsapp-bot/whatsapp-bot.ts

import type { Handler } from '@netlify/functions';
import { handleMessages, handleMessageEchoes, handleStandby } from './handlers';
import type { WhatsAppWebhookBody } from './types';
import { createLogger } from './utils/logger';

export const handler: Handler = async (
	event,
): Promise<{
	statusCode: number;
	body: string;
	headers?: Record<string, string>;
}> => {
	// 🔄 REFACTORED: Generate correlation ID at the start of each request
	const correlationId = crypto.randomUUID();
	const logger = createLogger(correlationId);

	const method = event.httpMethod;

	// 🔄 WEBHOOK VERIFICATION (GET)
	if (method === 'GET') {
		const params = event.queryStringParameters ?? {};
		const mode = params['hub.mode'] ?? params['hub_mode'];
		const challenge = params['hub.challenge'] ?? params['hub_challenge'];
		const verifyToken = params['hub.verify_token'] ?? params['hub_verify_token'];

		if (mode === 'subscribe' && verifyToken === process.env.WA_VERIFY_TOKEN) {
			logger.info('webhook_verified_success');
			return {
				statusCode: 200,
				headers: { 'Content-Type': 'text/plain' },
				body: challenge ?? '',
			};
		}

		logger.warn('webhook_verification_failed', {
			received_token: verifyToken,
			expected_token_prefix: process.env.WA_VERIFY_TOKEN?.slice(0, 8) + '...',
		});
		return { statusCode: 403, body: 'Verification failed' };
	}

	// 💬 MESSAGE HANDLING (POST)
	if (method === 'POST') {
		try {
			const body = JSON.parse(event.body ?? '{}') as WhatsAppWebhookBody;

			// 🔄 REFACTORED: Proper payload inspection instead of non-existent metadata.event_type
			const payload = body.entry?.[0]?.changes?.[0]?.value;

			logger.info('webhook_received', {
				entryCount: body.entry?.length ?? 0,
				hasMessages: !!payload?.messages?.length,
				hasStatuses: !!payload?.statuses?.length,
			});

			// Check for incoming messages or echoes
			if (payload?.messages && payload.messages.length > 0) {
				const phoneNumberId = process.env.WA_PHONE_NUMBER_ID;

				for (const msg of payload.messages) {
					// 🔄 REFACTORED: Route based on sender - echoes come from bot phone number
					if (msg.from === phoneNumberId) {
						logger.info('message_echo_detected', { messageId: msg.id, to: msg.from });
						return await handleMessageEchoes(body, { correlationId });
					} else {
						logger.info('incoming_message_detected', {
							messageId: msg.id,
							from: msg.from,
						});
						await handleMessages(body, correlationId);
					}
				}
			}

			// Check for delivery statuses
			if (payload?.statuses && payload.statuses.length > 0) {
				logger.info('delivery_status_received', { statusCount: payload.statuses.length });
				return { statusCode: 200, body: 'OK' };
			}

			// Unknown payload
			logger.warn('unknown_webhook_payload');
			return { statusCode: 200, body: 'OK' };
		} catch (error) {
			logger.error('router_error', { errorMessage: (error as Error).message });
			return { statusCode: 500, body: 'Error parsing webhook' };
		}
	}

	// Method not allowed
	return { statusCode: 405, body: 'Method Not Allowed' };
};
