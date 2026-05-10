import { Groq } from 'groq-sdk';
import { sendWaMessage, sendWaVideo } from './whatsapp';
import { loadHistory, saveHistory } from './storage';
import { loadProfile } from './profiles';
import { buildSystemPrompt } from './prompt-builder';
import { scheduleTask } from './scheduler';
import { info, error } from '../utils/logger';

const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });
const model = 'llama-3.1-8b-instant';

// 🔄 NEW: Regex patterns for custom actions
const VIDEO_REGEX = /<send\s+video(?:\s+([^\s>]+\.mp4))?>/i;
const DELAY_REGEX = /<message\s+(\d+)\s*(second|seconds|minute|minutes|hour|hours|h|m|s)>/i;

export async function handleUserMessage(
	correlationId: string,
	userPhone: string,
	userText: string,
	rawName: string,
	isGroup?: boolean,
): Promise<void> {
	const startTime = Date.now();

	try {
		// 1. Load Profile & History
		const profile = await loadProfile(userPhone);
		const history = await loadHistory(userPhone);

		// 2. Build Prompt
		const systemPrompt = buildSystemPrompt(profile, userText, isGroup);

		info('ai_prompt_generated', correlationId, {
			profileName: profile?.name || 'unknown',
			promptLength: systemPrompt.length,
			promptPreview: systemPrompt.slice(0, 50),
			isGroup: isGroup || false,
		});

		// 3. Call Groq
		info('ai_request_started', correlationId, {
			phone: userPhone,
			promptTokens: systemPrompt.length,
			historyLength: history.length,
			isGroup: isGroup || false,
		});

		const completion = await groq.chat.completions.create({
			messages: [
				{ role: 'system', content: systemPrompt },
				...history,
				{ role: 'user', content: userText },
			],
			model: model,
			temperature: 0.7,
			max_tokens: 300,
		});

		let cleanReply = completion.choices[0]?.message?.content?.trim() || '';

		if (!cleanReply) {
			throw new Error('Empty AI response');
		}

		info('ai_response_received', correlationId, {
			phone: userPhone,
			replyLength: cleanReply.length,
			modelUsed: model,
			durationMs: Date.now() - startTime,
		});

		// 🔄 NEW: Process Custom Action Tags BEFORE saving history or sending text

		// 1. Check for Video Send Tag: <send video> or <send video filename.mp4>
		const videoMatch = cleanReply.match(VIDEO_REGEX);
		if (videoMatch) {
			const filename = videoMatch[1] || 'long2.mp4'; // Default fallback if no name provided

			info('video_tag_detected', correlationId, {
				phone: userPhone,
				filename,
			});

			// Send video immediately
			// Note: In a real scenario, you might want to ensure this file exists in your public folder or S3
			await sendWaVideo(userPhone, filename, correlationId);

			// Remove the tag from the text reply so we don't show "<send video>" to the user
			cleanReply = cleanReply.replace(VIDEO_REGEX, '').trim();

			// If the reply is now empty (only contained the tag), stop here
			if (!cleanReply) {
				await saveHistory(userPhone, [
					{ role: 'user', content: userText },
					{ role: 'assistant', content: '[Sent Video]' },
				]);
				return;
			}
		}

		// 2. Check for Delayed Message Tag: <message 1 minute>
		const delayMatch = cleanReply.match(DELAY_REGEX);
		if (delayMatch && delayMatch[1] && delayMatch[2]) {
			const value = parseInt(delayMatch[1], 10);
			const unit = delayMatch[2].toLowerCase();

			// Calculate delay in milliseconds
			let delayMs = 0;
			if (unit.startsWith('s')) delayMs = value * 1000;
			else if (unit.startsWith('m')) delayMs = value * 60 * 1000;
			else if (unit.startsWith('h')) delayMs = value * 60 * 60 * 1000;

			info('delay_tag_detected', correlationId, {
				phone: userPhone,
				delayMs,
				originalUnit: unit,
			});

			// Extract the message content AFTER the tag
			// We split by the tag and take the second part, or just use the whole cleaned reply if preferred
			// Strategy: Remove tag from current reply, schedule the REMAINDER or a specific follow-up?
			// Prompt instruction usually implies: "Say this now, then say X later".
			// For simplicity: We schedule the CURRENT reply to be sent LATER, and acknowledge now.
			// OR: We send an ack now, and schedule the full reply.
			// Let's go with: Acknowledge now, schedule the generated response content (minus tag) for later.

			const messageContent =
				cleanReply.replace(DELAY_REGEX, '').trim() || '¡Aquí está tu mensaje programado!';

			await scheduleTask({
				phone: userPhone,
				message: messageContent,
				executeAt: Date.now() + delayMs,
				correlationId,
				isGroup: isGroup || false,
			});

			// Remove tag from current reply
			cleanReply = cleanReply.replace(DELAY_REGEX, '').trim();

			// Send immediate acknowledgment if there's remaining text, otherwise a standard ack
			if (cleanReply) {
				await sendWaMessage(userPhone, cleanReply,  correlationId );
			} else {
				await sendWaMessage(
					userPhone,
					`👌 Ok, te enviaré un mensaje en ${value} ${unit}.`,
					correlationId,
				);
			}

			await saveHistory(userPhone, [
				{ role: 'user', content: userText },
				{ role: 'assistant', content: `[Scheduled Message for ${delayMs}ms]` },
			]);
			return; // Exit early as the main reply is scheduled
		}

		// 4. Save History (if no special tags intercepted flow)
		await saveHistory(userPhone, [
			{ role: 'user', content: userText },
			{ role: 'assistant', content: cleanReply },
		]);

		// 5. Send Reply
		if (cleanReply) {
			await sendWaMessage(userPhone, cleanReply, correlationId);
		}
	} catch (err) {
		error('ai_generation_failed', correlationId, {
			phone: userPhone,
			errorMessage: err instanceof Error ? err.message : 'Unknown error',
			errorName: err instanceof Error ? err.name : 'Unknown',
		});

		await sendWaMessage(
			userPhone,
			'😅 Ups, mi cerebro se trabó un segundo. Intentá de nuevo.',
			correlationId,
		);
	}
}

export async function handleReorientationMessage(
	correlationId: string,
	userPhone: string,
	text: string,
	isGroup?: boolean,
): Promise<void> {
	// Reorientation messages (from cron) generally shouldn't trigger re-scheduling loops
	// We strip tags or ignore them in this context to prevent infinite loops
	try {
		const profile = await loadProfile(userPhone);
		const history = await loadHistory(userPhone);

		const systemPrompt = buildSystemPrompt(profile, text, isGroup);

		const completion = await groq.chat.completions.create({
			messages: [
				{ role: 'system', content: systemPrompt },
				...history,
				{ role: 'user', content: text },
			],
			model: 'llama-3.1-70b-versatile',
			temperature: 0.7,
			max_tokens: 300,
		});

		const cleanReply = completion.choices[0]?.message?.content?.trim();

		if (!cleanReply) {
			throw new Error('Empty AI response in reorientation');
		}

		await saveHistory(userPhone, [
			{ role: 'user', content: text },
			{ role: 'assistant', content: cleanReply },
		]);

		await sendWaMessage(userPhone, cleanReply, correlationId);

		info('scheduled_message_sent', correlationId, {
			phone: userPhone,
			chars: cleanReply.length,
		});
	} catch (err) {
		error('scheduled_message_failed', correlationId, {
			phone: userPhone,
			errorMessage: err instanceof Error ? err.message : 'Unknown error',
		});
	}
}
