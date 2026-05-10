// netlify/functions/whatsapp-bot/types.ts

export type MessageRole = 'system' | 'user' | 'assistant';
export type ChatStatus = 'active' | 'paused' | 'goodbye';

export interface ChatMessage {
	role: MessageRole;
	content: string;
	timestamp?: number; // For local storage only, not sent to AI
}

export interface UserState {
	status: ChatStatus;
	lastActive: number;
	nextProactiveTime?: number;
}

export interface UserProfile {
	name: string | null;
	knownSince: number;
	traits: string[];
	relationships: Record<string, string>;
	recentTopics: string[];
	lastInteraction: number;
	notes: string;
	state: UserState;
}

export interface WhatsAppMessage {
	id: string; // 🔄 REFACTORED: Explicitly ensuring ID is present for typing flow
	from: string;
	timestamp: string;
	type: 'text' | 'audio' | 'image' | 'video' | 'document';
	text?: {
		body: string;
	};
	audio?: {
		id: string;
		mime_type: string;
		voice?: boolean;
	};
	image?: {
		id: string;
		mime_type: string;
		caption?: string;
	};
	video?: {
		id: string;
		mime_type: string;
		caption?: string;
	};
	document?: {
		id: string;
		filename: string;
		mime_type: string;
		caption?: string;
	};
}

export interface WhatsAppContact {
	profile: { name: string };
	wa_id: string;
}

export interface ScheduledTask {
	id: string;
	userId: string;
	// The message to send to the AI as a "system" reorientation prompt
	reorientPrompt: string;
	// The last user message for context
	lastUserMessage: string;
	triggerAt: number;
	createdAt: number;
	// Optional: original marker text for debugging
	originalMarker?: string;
}

export interface WhatsAppChange {
	value: {
		messaging_product: string;
		metadata: {
			display_phone_number: string;
			phone_number_id: string;
			event_type?: 'messages' | 'message_echoes' | 'standby';
		};
		contacts?: WhatsAppContact[];
		messages?: WhatsAppMessage[];
		statuses?: any[];
		errors?: any[];
	};
	field: string;
}

export interface WhatsAppEntry {
	id: string;
	changes: WhatsAppChange[];
}

export interface WhatsAppWebhookBody {
	object: string;
	entry: WhatsAppEntry[];
}

export interface HandlerResponse {
	statusCode: number;
	body: string;
	headers?: Record<string, string>;
}

export interface WhatsAppBody {
	object: string;
	entry: Entry[];
}

export interface Entry {
	id: string;
	changes: Change[];
}

export interface Change {
	value: Value;
	field: string;
}

export interface Value {
	messaging_product: string;
	metadata: {
		display_phone_number: string;
		phone_number_id: string;
	};
	contacts?: Contact[];
	messages?: WhatsAppMessage[];
	statuses?: Status[];
}

export interface Contact {
	profile: {
		name: string;
	};
	wa_id: string;
}

export interface Status {
	id: string;
	status: 'sent' | 'delivered' | 'read' | 'failed';
	timestamp: string;
	recipient_id: string;
	conversation?: {
		id: string;
		origin: {
			type: 'user_initiated' | 'business_initiated' | 'referral_conversion';
		};
	};
	pricing?: {
		billable: boolean;
		category: string;
	};
}
