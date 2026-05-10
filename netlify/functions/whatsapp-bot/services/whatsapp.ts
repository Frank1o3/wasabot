import axios from 'axios';
import { info, error } from '../utils/logger';

const WA_BASE_URL = 'https://graph.facebook.com/v25.0';
const WA_PHONE_NUMBER_ID = process.env.WA_PHONE_NUMBER_ID;
const WA_ACCESS_TOKEN = process.env.WA_ACCESS_TOKEN;

// 🔄 UPDATED: Added optional filename parameter
export async function sendWaVideo(
	to: string,
	filename: string,
	correlationId?: string,
): Promise<void> {
	if (!WA_PHONE_NUMBER_ID || !WA_ACCESS_TOKEN) {
		error('missing_whatsapp_creds', correlationId, {
			detail: 'WA_PHONE_NUMBER_ID or WA_ACCESS_TOKEN missing',
		});
		return;
	}

	// Assuming videos are hosted publicly or in Netlify Blobs with a known URL
	// For this example, we assume a public URL structure or a local asset path resolved to URL
	// If you have actual video IDs from WhatsApp Media API, use that logic instead.
	// Here we simulate sending a video by URL.

	// IMPORTANT: WhatsApp requires the video to be uploaded first to get an ID,
	// OR you can send by URL if it's publicly accessible.
	// Let's assume we are sending by URL for simplicity as per previous constraints.
	const videoUrl = `https://insulin-church-trainers-controversy.trycloudflare.com/videos/${filename}`; // Replace with your actual hosting logic

	const payload = {
		messaging_product: 'whatsapp',
		to,
		type: 'video',
		video: {
			link: videoUrl,
			caption: '🎬 ¡Mira esto!',
		},
	};

	try {
		const response = await axios.post(
			`${WA_BASE_URL}/${WA_PHONE_NUMBER_ID}/messages`,
			payload,
			{
				headers: {
					Authorization: `Bearer ${WA_ACCESS_TOKEN}`,
					'Content-Type': 'application/json',
				},
			},
		);

		info('video_message_sent', correlationId, {
			phone: to,
			filename,
			messageId: response.data.messages?.[0]?.id,
		});
	} catch (err: any) {
		error('video_send_failed', correlationId, {
			phone: to,
			filename,
			status: err.response?.status,
			data: err.response?.data,
		});
		throw err;
	}
}

export async function sendWaMessage(
	to: string,
	text: string,
	correlationId?: string,
): Promise<void> {
	if (!WA_PHONE_NUMBER_ID || !WA_ACCESS_TOKEN) {
		error('missing_whatsapp_creds', correlationId, {
			detail: 'WA_PHONE_NUMBER_ID or WA_ACCESS_TOKEN missing',
		});
		return;
	}

	const payload = {
		messaging_product: 'whatsapp',
		to,
		type: 'text',
		text: { body: text },
	};

	try {
		const response = await axios.post(
			`${WA_BASE_URL}/${WA_PHONE_NUMBER_ID}/messages`,
			payload,
			{
				headers: {
					Authorization: `Bearer ${WA_ACCESS_TOKEN}`,
					'Content-Type': 'application/json',
				},
			},
		);

		info('text_message_sent', correlationId, {
			phone: to,
			messageId: response.data.messages?.[0]?.id,
			charCount: text.length,
		});
	} catch (err: any) {
		error('text_send_failed', correlationId, {
			phone: to,
			status: err.response?.status,
			data: err.response?.data,
		});
		throw err;
	}
}
