// netlify/functions/whatsapp-bot/utils/logger.ts

/**
 * Structured logger for serverless functions
 * Outputs strict JSON format for easy parsing in log aggregators
 * Synchronous, no I/O, cold-start friendly
 */

export interface LogMeta {
	userId?: string;
	phone?: string;
	event?: string;
	[key: string]: unknown;
}

const formatLog = (
	level: 'info' | 'warn' | 'error',
	eventName: string,
	correlationId: string | undefined,
	meta?: LogMeta,
): string => {
	// 🔄 FIXED LOGGER: Extract correlationId from meta if passed there, ensure it's always a string
	const extractedCorrelationId =
		typeof meta?.correlationId === 'string'
			? meta.correlationId
			: typeof correlationId === 'string'
				? correlationId
				: 'no-correlation-id';

	const logObj: Record<string, unknown> = {
		level,
		event: eventName,
		correlationId: extractedCorrelationId,
		timestamp: new Date().toISOString(),
	};

	// Add meta fields except correlationId (already added above)
	if (meta) {
		Object.entries(meta).forEach(([key, value]) => {
			if (key !== 'correlationId' && value !== undefined) {
				logObj[key] = value;
			}
		});
	}

	return JSON.stringify(logObj);
};

export const info = (eventName: string, correlationId?: string, meta?: LogMeta): void => {
	console.log(formatLog('info', eventName, correlationId, meta));
};

export const warn = (eventName: string, correlationId?: string, meta?: LogMeta): void => {
	console.log(formatLog('warn', eventName, correlationId, meta));
};

export const error = (eventName: string, correlationId?: string, meta?: LogMeta): void => {
	console.error(formatLog('error', eventName, correlationId, meta));
};

/**
 * Creates a logger instance bound to a specific correlation ID
 * 🔄 FIXED LOGGER: Simplified interface - accepts meta object directly
 */
export const createLogger = (correlationId: string) => ({
	info: (eventName: string, meta?: LogMeta) => info(eventName, correlationId, meta),
	warn: (eventName: string, meta?: LogMeta) => warn(eventName, correlationId, meta),
	error: (eventName: string, meta?: LogMeta) => error(eventName, correlationId, meta),
});
