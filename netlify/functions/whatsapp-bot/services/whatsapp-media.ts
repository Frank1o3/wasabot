// netlify/functions/whatsapp-bot/services/whatsapp-media.ts

import { createLogger } from '../utils/logger';

const BASE_URL = `https://graph.facebook.com/v25.0`;

interface MediaResponse {
	url: string;
	mime_type: string;
}

/**
 * Gets the media URL and MIME type for a given media ID
 * @param mediaId - The media ID from WhatsApp webhook
 * @returns Object with url and mimeType, or null if failed
 */
export const getMediaUrl = async (
	mediaId: string,
	context?: { correlationId?: string },
): Promise<{ url: string; mimeType: string } | null> => {
	const logger = createLogger(context?.correlationId || 'no-correlation-id');

	try {
		const response = await fetch(`${BASE_URL}/${mediaId}`, {
			method: 'GET',
			headers: {
				Authorization: `Bearer ${process.env.WA_ACCESS_TOKEN}`,
			},
		});

		if (!response.ok) {
			if (response.status === 404) {
				logger.warn('media_not_found', { mediaId, status: 404 });
				return null;
			}
			throw new Error(`Media API error: ${response.status} ${response.statusText}`);
		}

		const data = (await response.json()) as MediaResponse;

		if (!data.url || !data.mime_type) {
			logger.warn('media_response_missing_fields', {
				mediaId,
				hasUrl: !!data.url,
				hasMimeType: !!data.mime_type,
			});
			return null;
		}

		logger.info('media_url_retrieved', { mediaId, mimeType: data.mime_type });
		return { url: data.url, mimeType: data.mime_type };
	} catch (error) {
		logger.error('getMediaUrl_error', { mediaId, errorMessage: (error as Error).message });
		return null;
	}
};

/**
 * Downloads media from a URL and returns as Buffer
 * @param url - The media URL from getMediaUrl
 * @returns Buffer with raw media data, or null if failed
 */
export const downloadMedia = async (
	url: string,
	context?: { correlationId?: string },
): Promise<Buffer | null> => {
	const logger = createLogger(context?.correlationId || 'no-correlation-id');

	try {
		const response = await fetch(url, {
			method: 'GET',
			headers: {
				Authorization: `Bearer ${process.env.WA_ACCESS_TOKEN}`,
			},
		});

		if (!response.ok) {
			if (response.status === 404 || response.status === 403) {
				logger.warn('media_download_failed_expired', {
					url: url.slice(0, 50),
					status: response.status,
				});
				return null;
			}
			throw new Error(`Media download error: ${response.status} ${response.statusText}`);
		}

		const arrayBuffer = await response.arrayBuffer();
		const buffer = Buffer.from(arrayBuffer);

		logger.info('media_downloaded', { sizeBytes: buffer.length, urlPreview: url.slice(0, 50) });
		return buffer;
	} catch (error) {
		logger.error('downloadMedia_error', {
			url: url.slice(0, 50),
			errorMessage: (error as Error).message,
		});
		return null;
	}
};
