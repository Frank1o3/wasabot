// netlify/functions/whatsapp-bot/utils/auth.ts

/**
 * Checks if a phone number is in the allowed list.
 * If ALLOWED_PHONES is empty, all numbers are allowed.
 */
export const isPhoneAllowed = (phone: string): boolean => {
	const allowedList = (process.env.ALLOWED_PHONES || '')
		.split(',')
		.map((p) => p.trim())
		.filter((p) => p.length > 0);

	// Empty list = allow all (development mode)
	return allowedList.length === 0 || allowedList.includes(phone);
};

/**
 * Logs a blocked access attempt (silent fail for privacy)
 */
export const logBlockedAccess = (phone: string, userName?: string): void => {
	console.log(
		JSON.stringify({
			level: 'warn',
			event: 'access_blocked',
			phone,
			userName: userName || 'unknown',
			reason: 'not_in_allowed_list',
		}),
	);
};
