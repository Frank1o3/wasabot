// netlify/functions/cron-check.ts
import type { Handler } from '@netlify/functions';
import { getDueTasks, deleteTask, cleanupLocalTasks } from './whatsapp-bot/services/scheduler.js';
import { handleReorientationMessage } from './whatsapp-bot/services/ai.js';
import { createLogger } from './whatsapp-bot/utils/logger.js';

const CRON_SECRET = process.env.CRON_SECRET || 'changeme_in_production';

export const handler: Handler = async (event) => {
	// 🔄 REFACTORED: Generate correlation ID for cron execution
	const correlationId = crypto.randomUUID();
	const logger = createLogger(correlationId);

	const secret = event.headers['x-cron-secret'] || event.queryStringParameters?.secret;
	if (secret !== CRON_SECRET) {
		logger.warn('cron_unauthorized', { provided_secret: secret ? 'present' : 'missing' });
		return { statusCode: 401, body: 'Unauthorized' };
	}

	logger.info('cron_check_started');

	// Cleanup old local tasks (dev only)
	cleanupLocalTasks();

	const tasks = await getDueTasks();

	for (const task of tasks) {
		try {
			logger.info('cron_processing_task', { taskId: task.id, userId: task.userId });
			await handleReorientationMessage(task.userId, task.reorientPrompt, correlationId);
			await deleteTask(task.id);
			logger.info('cron_task_completed', { taskId: task.id });
		} catch (err) {
			logger.error('cron_task_failed', {
				taskId: task.id,
				errorMessage: (err as Error).message,
			});
			// Delete failed task to avoid infinite retry loop in dev
			await deleteTask(task.id);
		}
		await new Promise((res) => setTimeout(res, 1500)); // Rate limit
	}

	return { statusCode: 200, body: `Processed ${tasks.length} tasks` };
};
