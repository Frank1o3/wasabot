import { Groq } from 'groq-sdk';
import { getMediaUrl, downloadMedia } from './whatsapp-media';
import { sendWaMessage } from './whatsapp';
import { handleUserMessage } from './ai'; // Reuse AI logic
import { info, warn, error } from '../utils/logger';
import type { WhatsAppMessage } from '../types';

const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

const MAX_AUDIO_SIZE_MB = 5;

/**
 * Transcribes audio and passes to AI.
 * 🔄 FIXED PROMPT INTEGRATION: Added isGroup param.
 */
export async function transcribeAndRespond(
	msg: WhatsAppMessage,
	userPhone: string,
	rawName: string,
	incomingMessageId: string,
	correlationId: string,
	isGroup?: boolean, // 🔄 FIXED: Added isGroup
): Promise<void> {
	const audioId = msg.audio?.id;
	if (!audioId) {
		warn('missing_audio_id', correlationId, { phone: userPhone });
		return;
	}

	try {
		const mediaData = await getMediaUrl(audioId, { correlationId });
		if (!mediaData) {
			throw new Error('Failed to get media URL');
		}

		const buffer = await downloadMedia(mediaData.url, { correlationId });

		const sizeMB = buffer.length / (1024 * 1024);
		if (sizeMB > MAX_AUDIO_SIZE_MB) {
			warn('audio_too_large', correlationId, { phone: userPhone, sizeMB });
			await sendWaMessage(
				userPhone,
				'🎤 Ese audio es muy largo, ¿podés resumirlo o escribirlo?',
				correlationId ,
			);
			return;
		}

		const text = await transcribeAudio(buffer, mediaData.mimeType, correlationId);

		if (!text || text.trim().length === 0) {
			warn('empty_transcription', correlationId, { phone: userPhone });
			await sendWaMessage(userPhone, 'No pude escuchar el audio bien 😅 ¿podés escribirlo?',
				correlationId,
			);
			return;
		}

		info('voice_message_transcribed', correlationId, {
			phone: userPhone,
			textPreview: text.slice(0, 30),
			isGroup,
		});

		// 🔄 FIXED PROMPT INTEGRATION: Pass isGroup to handleUserMessage
		await handleUserMessage(correlationId, userPhone, text, rawName, isGroup);
	} catch (audioError) {
		error('audio_processing_failed', correlationId, {
			phone: userPhone,
			error: audioError instanceof Error ? audioError.message : 'Unknown audio error',
		});

		await sendWaMessage(userPhone, 'Tuve problemas procesando el audio 🎧 ¿Me lo escribís?',
			correlationId,
		);
	}
}

async function transcribeAudio(
	buffer: Buffer,
	mimeType: string,
	correlationId: string,
): Promise<string | null> {
	try {
		const blob = new Blob([buffer], { type: mimeType });
		const file = new File([blob], 'voice.ogg', { type: mimeType });

		const transcription = await groq.audio.transcriptions.create({
			file,
			model: 'whisper-large-v3-turbo',
			language: 'es',
		});

		return transcription.text || null;
	} catch (err) {
		error('groq_transcription_error', correlationId, {
			error: err instanceof Error ? err.message : 'Groq API error',
		});
		return null;
	}
}
