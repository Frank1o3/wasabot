import type { WhatsAppBody } from '../types';
import { handleUserMessage } from '../services/ai';
import { info, warn, error } from '../utils/logger';

/**
 * Main entry point for incoming user messages.
 * 🔄 FIXED PROMPT INTEGRATION: Extracts isGroup and passes it to handlers.
 */
export async function handleMessages(body: WhatsAppBody, correlationId: string): Promise<void> {
	const payload = body.entry?.[0]?.changes?.[0]?.value;
	const messages = payload?.messages;

	if (!messages || messages.length === 0) {
		warn('no_messages_in_payload', correlationId, { detail: 'Empty messages array' });
		return;
	}

	for (const msg of messages) {
		// Skip non-user messages (status updates etc handled elsewhere)
		if (msg.from === process.env.WA_PHONE_NUMBER_ID) {
			continue;
		}

		const userPhone = msg.from;

		// 🔄 FIXED PROMPT INTEGRATION: Extract group_id and compute isGroup
		const groupId = (msg as any).group_id; // Cast for safety if type isn't updated yet
		const isGroup = !!groupId;

		const rawName =
			payload?.contacts?.find((c) => c.wa_id === userPhone)?.profile?.name || 'Usuario';
		const incomingMessageId = msg.id;

		try {
			if (msg.type === 'text') {
				const userText = msg.text?.body || '';

				info('text_message_received', correlationId, {
					phone: userPhone,
					name: rawName,
					textPreview: userText.slice(0, 30),
					isGroup,
					groupId: groupId || undefined,
				});

				// 🔄 FIXED PROMPT INTEGRATION: Pass isGroup to handler
				await handleUserMessage(correlationId, userPhone, userText, rawName, isGroup);
			} else if (msg.type === 'audio' && msg.audio?.voice === true) {
				info('voice_message_received', correlationId, {
					phone: userPhone,
					audioId: msg.audio.id,
					isGroup,
				});

				const { transcribeAndRespond } = await import('../services/audio');
				await transcribeAndRespond(
					msg,
					userPhone,
					rawName,
					incomingMessageId,
					correlationId,
				);
			} else {
				warn('unsupported_message_type', correlationId, {
					phone: userPhone,
					type: msg.type,
					isGroup,
				});
			}
		} catch (handlerError) {
			error('message_handler_crash', correlationId, {
				phone: userPhone,
				error:
					handlerError instanceof Error ? handlerError.message : 'Unknown handler error',
				isGroup,
			});
		}
	}
}
