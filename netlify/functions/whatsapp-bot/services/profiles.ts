// netlify/functions/whatsapp-bot/services/profiles.ts

import { getStore, type Store } from '@netlify/blobs';
import type { UserProfile, ChatStatus } from '../types';

const localProfiles = new Map<string, UserProfile>();
let profileStore: Store | null | undefined;

const getStoreInstance = async (): Promise<Store | null> => {
	if (profileStore !== undefined) return profileStore;
	try {
		const store = getStore({ name: 'profiles', consistency: 'eventual' });
		await store.set('__ping__', 'ok');
		await store.delete('__ping__');
		profileStore = store;
		return store;
	} catch {
		profileStore = null;
		return null;
	}
};

export const loadProfile = async (userId: string): Promise<UserProfile | null> => {
	const store = await getStoreInstance();
	if (store) {
		try {
			const raw = (await store.get(`profile:${userId}`)) as unknown as string | null;
			return raw ? JSON.parse(raw) : null;
		} catch {}
	}
	return localProfiles.get(userId) || null;
};

export const saveProfile = async (userId: string, profile: UserProfile): Promise<void> => {
	const store = await getStoreInstance();
	const data = { ...profile, lastInteraction: Date.now() };
	if (store) {
		try {
			await store.set(`profile:${userId}`, JSON.stringify(data));
			return;
		} catch {}
	}
	localProfiles.set(userId, data);
};

export const updateChatStatus = async (userId: string, status: ChatStatus): Promise<void> => {
	let profile = await loadProfile(userId);
	profile = ensureProfileState(profile); // ← Ensure state exists

	profile.state.status = status;
	profile.state.lastActive = Date.now();
	await saveProfile(userId, profile);
};

export const extractFactsFromMessage = (
	userText: string,
	existingProfile: UserProfile | null,
): Partial<UserProfile> => {
	const text = userText.toLowerCase();
	const updates: Partial<UserProfile> = {};

	const nameMatch = text.match(/(?:me llamo|soy|mi nombre es|me dicen)\s+([a-záéíóúñ\s]{2,20})/i);
	if (nameMatch && nameMatch[1] && (!existingProfile?.name || existingProfile.name === 'Amigo')) {
		updates.name = nameMatch[1].trim();
	}

	const ageMatch = text.match(/(?:tengo|soy de)\s+(\d{1,2})\s*(?:años|grado)/i);
	if (
		ageMatch &&
		ageMatch[1] &&
		!existingProfile?.traits?.some((t) => t.match(/\d+\s*(años|grado)/i))
	) {
		updates.traits = [
			...(existingProfile?.traits || []),
			`${ageMatch[1]} ${text.includes('grado') ? 'grado' : 'años'}`,
		];
	}

	const interests = [
		'programación',
		'python',
		'java',
		'c++',
		'gaming',
		'música',
		'gym',
		'vape',
		'cine',
		'anime',
		'fútbol',
		'coche',
		'moto',
	];
	const foundTopics = interests.filter((i) => text.includes(i));
	if (foundTopics.length > 0) {
		updates.recentTopics = [...(existingProfile?.recentTopics || []), ...foundTopics].slice(
			-10,
		);
	}

	return updates;
};

/**
 * Ensures a UserProfile has all required fields, especially `state`
 */
export const ensureProfileState = (profile: UserProfile | null): UserProfile => {
	if (!profile) {
		return {
			name: null,
			knownSince: Date.now(),
			traits: [],
			relationships: {},
			recentTopics: [],
			lastInteraction: Date.now(),
			notes: '',
			state: { status: 'active', lastActive: Date.now() },
		};
	}

	// Ensure state exists and has defaults
	return {
		...profile,
		state: {
			status: profile.state?.status || 'active',
			lastActive: profile.state?.lastActive || Date.now(),
			nextProactiveTime: profile.state?.nextProactiveTime,
		},
	};
};
