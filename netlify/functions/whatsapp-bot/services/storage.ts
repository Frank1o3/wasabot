// netlify/functions/whatsapp-bot/services/storage.ts

import { getStore, type Store } from '@netlify/blobs';
import type { ChatMessage } from '../types';

// 🔄 Fallback: In-memory storage for local dev when Blobs isn't available
const localMemory = new Map<string, { messages: ChatMessage[]; expires: number }>();
const MEMORY_TTL = 30 * 60 * 1000; // 30 minutes

let convoStore: Store | null | undefined;

/**
 * Initializes Netlify Blobs store with a ping test
 */
export const getConvoStore = async (): Promise<Store | null> => {
	if (convoStore !== undefined) return convoStore;

	try {
		const store = getStore({
			name: 'conversations',
			consistency: 'eventual',
		});
		// Ping test to verify Blobs is working
		await store.set('__ping__', Date.now().toString());
		await store.delete('__ping__');
		convoStore = store;
		console.log('✅ Netlify Blobs initialized');
		return store;
	} catch {
		console.log('⚠️ Blobs no disponible (dev local?), usando memoria fallback');
		convoStore = null;
		return null;
	}
};

/**
 * Generates storage key based on conversation type (DM or group)
 * 🔄 REFACTORED: Added group support for isolated storage
 */
const getStorageKey = (userId: string, groupId?: string): string => {
	// 🔄 REFACTORED: Group conversations use separate namespace
	if (groupId) {
		return `convo:group:${groupId}`;
	}
	return `convo:${userId}`;
};

/**
 * Loads conversation history for a user or group (Blobs → fallback → empty)
 * 🔄 REFACTORED: Added groupId parameter for group message support
 */
export const loadHistory = async (userId: string, groupId?: string): Promise<ChatMessage[]> => {
	const now = Date.now();
	const storageKey = getStorageKey(userId, groupId);

	// Clean expired local memory entries
	for (const [key, val] of localMemory.entries()) {
		if (val.expires < now) localMemory.delete(key);
	}

	// Try Blobs first
	if (convoStore) {
		try {
			const raw = await convoStore.get(storageKey);
			if (raw) {
				const text =
					typeof raw === 'string' ? raw : new TextDecoder().decode(raw as ArrayBuffer);
				const parsed = JSON.parse(text) as ChatMessage[];
				console.log(`📦 [Blobs] Loaded ${parsed.length} mensajes para ${storageKey}`);
				return parsed;
			}
		} catch (error) {
			console.warn(`⚠️ Blobs load falló para ${storageKey}: ${(error as Error).message}`);
		}
	}

	// Fallback to local memory
	const entry = localMemory.get(storageKey);
	if (entry && entry.expires > Date.now()) {
		console.log(`📦 [Local] Loaded ${entry.messages.length} mensajes para ${storageKey}`);
		return entry.messages;
	}

	return [];
};

/**
 * Saves conversation history (trim to last 16 messages)
 * 🔄 REFACTORED: Added groupId parameter for group message support
 */
export const saveHistory = async (
	userId: string,
	messages: ChatMessage[],
	groupId?: string,
): Promise<void> => {
	const trimmed = messages.slice(-16); // Keep context window manageable
	const storageKey = getStorageKey(userId, groupId);

	// Try Blobs first
	if (convoStore) {
		try {
			await convoStore.set(storageKey, JSON.stringify(trimmed));
			console.log(`💾 [Blobs] Guardados ${trimmed.length} mensajes para ${storageKey}`);
			return;
		} catch (error) {
			console.warn(`⚠️ Blobs save falló para ${storageKey}: ${(error as Error).message}`);
		}
	}

	// Fallback to local memory
	localMemory.set(storageKey, {
		messages: trimmed,
		expires: Date.now() + MEMORY_TTL,
	});
	console.log(`💾 [Local] Guardados ${trimmed.length} mensajes para ${storageKey}`);
};
