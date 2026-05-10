// netlify/functions/whatsapp-bot/services/scheduler.ts

import { getStore, type Store } from '@netlify/blobs';
import type { ScheduledTask } from '../types';
import * as fs from 'fs';
import * as path from 'path';
import { createLogger } from '../utils/logger';

// 🔄 Fallback: File-based task queue for local dev when Blobs isn't available
const LOCAL_TASKS_FILE = path.join(process.cwd(), '.netlify', 'local-tasks.json');
let schedulerStore: Store | null | undefined;

// Ensure local tasks directory exists
const ensureLocalDir = (): void => {
	const dir = path.dirname(LOCAL_TASKS_FILE);
	if (!fs.existsSync(dir)) {
		fs.mkdirSync(dir, { recursive: true });
	}
};

// Load tasks from local file
const loadLocalTasks = (): Map<string, ScheduledTask> => {
	const tasks = new Map<string, ScheduledTask>();
	try {
		if (fs.existsSync(LOCAL_TASKS_FILE)) {
			const raw = fs.readFileSync(LOCAL_TASKS_FILE, 'utf-8');
			const parsed = JSON.parse(raw) as Record<string, ScheduledTask>;
			for (const [id, task] of Object.entries(parsed)) {
				tasks.set(id, task);
			}
			const logger = createLogger('scheduler-local');
			logger.info('local_tasks_loaded', { count: tasks.size });
		}
	} catch (error) {
		const logger = createLogger('scheduler-local');
		logger.warn('local_tasks_load_failed', { errorMessage: (error as Error).message });
	}
	return tasks;
};

// Save tasks to local file
const saveLocalTasks = (tasks: Map<string, ScheduledTask>): void => {
	try {
		ensureLocalDir();
		const obj = Object.fromEntries(tasks);
		fs.writeFileSync(LOCAL_TASKS_FILE, JSON.stringify(obj, null, 2), 'utf-8');
	} catch (err) {
		const logger = createLogger('scheduler-local');
		logger.warn('local_tasks_save_failed', { errorMessage: (err as Error).message });
	}
};

const getSchedulerStore = async (): Promise<Store | null> => {
	if (schedulerStore !== undefined) return schedulerStore;
	try {
		const store = getStore({ name: 'scheduler', consistency: 'strong' });
		await store.set('__ping__', 'ok');
		await store.delete('__ping__');
		schedulerStore = store;
		const logger = createLogger('scheduler-blobs');
		logger.info('blobs_initialized');
		return store;
	} catch {
		const logger = createLogger('scheduler-blobs');
		logger.warn('blobs_unavailable_using_fallback');
		schedulerStore = null;
		return null;
	}
};

export const addScheduledTask = async (
	userId: string,
	reorientPrompt: string,
	lastUserMessage: string,
	delayMs: number,
): Promise<void> => {
	const logger = createLogger('scheduler-add');
	const task: ScheduledTask = {
		id: `${userId}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
		userId,
		reorientPrompt,
		lastUserMessage,
		triggerAt: Date.now() + delayMs,
		createdAt: Date.now(),
	};

	const store = await getSchedulerStore();

	if (store) {
		try {
			await store.set(`task:${task.id}`, JSON.stringify(task));
			logger.info('task_scheduled_blobs', { taskId: task.id, userId, delayMs });
			return;
		} catch (error) {
			logger.warn('blobs_schedule_failed', { errorMessage: (error as Error).message });
		}
	}

	// Fallback to file-based storage
	ensureLocalDir();
	const tasks = loadLocalTasks();
	tasks.set(task.id, task);
	saveLocalTasks(tasks);
	logger.info('task_scheduled_local', { taskId: task.id, userId, delayMs });
};

/**
 * 🔄 FIX: Wrapper function to match the calling convention used in ai.ts
 * Accepts an object with phone, message, executeAt, correlationId, isGroup
 */
export const scheduleTask = async (params: {
	phone: string;
	message: string;
	executeAt: number;
	correlationId: string;
	isGroup: boolean;
}): Promise<void> => {
	const { phone, message, executeAt, correlationId, isGroup } = params;
	const delayMs = executeAt - Date.now();

	// Use the message as both reorientPrompt and lastUserMessage for simple scheduled messages
	await addScheduledTask(phone, message, message, Math.max(0, delayMs));

	const logger = createLogger('scheduler-scheduleTask');
	logger.info('task_scheduled_via_wrapper', {
		phone,
		executeAt,
		delayMs,
		correlationId,
		isGroup,
	});
};

export const getDueTasks = async (): Promise<ScheduledTask[]> => {
	const logger = createLogger('scheduler-getdue');
	const store = await getSchedulerStore();
	const dueTasks: ScheduledTask[] = [];
	const now = Date.now();

	if (store) {
		try {
			const result = await store.list({ prefix: 'task:' });
			for (const blob of result.blobs) {
				const raw = await store.get(blob.key, { type: 'text' });
				if (!raw) continue;
				const task = JSON.parse(raw) as ScheduledTask;
				if (task.triggerAt <= now) {
					dueTasks.push(task);
				}
			}
			logger.info('due_tasks_found_blobs', { count: dueTasks.length });
			return dueTasks;
		} catch (error) {
			logger.warn('blobs_getdue_failed', { errorMessage: (error as Error).message });
		}
	}

	// Fallback to file-based storage
	const tasks = loadLocalTasks();
	for (const [_, task] of tasks.entries()) {
		if (task.triggerAt <= now) {
			dueTasks.push(task);
		}
	}
	logger.info('due_tasks_found_local', { count: dueTasks.length });
	return dueTasks;
};

export const deleteTask = async (taskId: string): Promise<void> => {
	const logger = createLogger('scheduler-delete');
	const store = await getSchedulerStore();

	if (store) {
		try {
			await store.delete(`task:${taskId}`);
			logger.info('task_deleted_blobs', { taskId });
			return;
		} catch (error) {
			logger.warn('blobs_delete_failed', { errorMessage: (error as Error).message });
		}
	}

	// Fallback to file-based storage
	const tasks = loadLocalTasks();
	if (tasks.delete(taskId)) {
		saveLocalTasks(tasks);
		logger.info('task_deleted_local', { taskId });
	}
};

/**
 * Clear expired tasks from local file (call periodically in dev)
 */
export const cleanupLocalTasks = (): void => {
	const logger = createLogger('scheduler-cleanup');
	const now = Date.now();
	const tasks = loadLocalTasks();
	let deleted = 0;

	for (const [id, task] of tasks.entries()) {
		// Keep tasks for 1 hour after trigger time for debugging
		if (task.triggerAt + 3600000 < now) {
			tasks.delete(id);
			deleted++;
		}
	}

	if (deleted > 0) {
		saveLocalTasks(tasks);
		logger.info('tasks_cleaned_up', { count: deleted });
	}
};
