"""
Background scheduler using APScheduler for polling and executing scheduled tasks.

🐍 PYTHON NATIVE: APScheduler with asyncio integration, 5-second polling interval
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from wasabot.services.db import delete_task, get_due_tasks
from wasabot.services.logger import CorrelationContext, get_logger
from wasabot.services.whatsapp_api import get_whatsapp_client

logger = get_logger(__name__)


class TaskScheduler:
    """
    Background task scheduler that polls SQLite for due tasks.

    Runs every 5 seconds to check for and execute scheduled messages.
    """

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()
        self._whatsapp_client = get_whatsapp_client()
        self._running = False

    def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            logger.warning("scheduler_already_running")
            return

        # Add polling job - runs every 5 seconds
        self._scheduler.add_job(
            self._poll_and_execute,
            trigger=IntervalTrigger(seconds=5),
            id="task_poller",
            name="Poll and execute scheduled tasks",
            replace_existing=True,
        )

        self._scheduler.start()
        self._running = True
        logger.info("scheduler_started | interval=5s")

    def stop(self) -> None:
        """Stop the scheduler."""
        if not self._running:
            return

        self._scheduler.shutdown(wait=False)
        self._running = False
        logger.info("scheduler_stopped")

    async def _poll_and_execute(self) -> None:
        """Poll database for due tasks and execute them."""
        try:
            current_time = int(datetime.now(UTC).timestamp())
            due_tasks = get_due_tasks(current_time)

            if not due_tasks:
                logger.debug("scheduler_poll_no_due_tasks")
                return

            logger.info(f"scheduler_poll_executing | count={len(due_tasks)}")

            # Execute each due task
            for task in due_tasks:
                await self._execute_task(task)

        except Exception as e:
            logger.error(f"scheduler_poll_failed | error={e!s}")

    async def _execute_task(self, task: dict[str, Any]) -> None:
        """
        Execute a single scheduled task.

        Args:
            task: Task dict from database
        """
        task_id = task["task_id"]
        wa_id = task["wa_id"]
        message = task["message"]
        correlation_id = task.get("correlation_id")
        # 🎬 DELAYED VIDEO: New fields for video actions
        action = task.get("action", "send_message")
        video_url = task.get("video_url")
        caption = task.get("caption")
        # 👤 HUMANITY FEATURE: Contextual reply support for scheduled tasks
        reply_to_message_id = task.get("reply_to_message_id")

        # Set correlation ID for this task's context
        with CorrelationContext(correlation_id):
            try:
                logger.info(
                    f"scheduled_task_executing | task_id={task_id} | wa_id={wa_id} | action={action}"
                )

                # 🎬 DELAYED VIDEO: Handle different action types
                if action == "send_video":
                    # Send video task
                    if video_url:
                        success = await self._whatsapp_client.send_video(
                            wa_id,
                            video_url,
                            caption=caption,
                            reply_to_message_id=reply_to_message_id,  # 👤 HUMANITY FEATURE: Contextual reply
                        )
                    else:
                        logger.error(f"scheduled_video_task_missing_url | task_id={task_id}")
                        success = False
                else:
                    # Default: send text message
                    success = await self._whatsapp_client.send_text(
                        wa_id,
                        message,
                        reply_to_message_id=reply_to_message_id,  # 👤 HUMANITY FEATURE: Contextual reply
                    )

                if success:
                    logger.info(f"scheduled_task_completed | task_id={task_id}")
                else:
                    logger.error(f"scheduled_task_send_failed | task_id={task_id}")

            except Exception as e:
                logger.error(f"scheduled_task_execution_failed | task_id={task_id} | error={e!s}")
            finally:
                # Always delete task after execution (success or failure)
                # This prevents infinite loops on persistent failures
                delete_task(task_id)
                logger.debug(f"scheduled_task_deleted | task_id={task_id}")


# Global scheduler instance
_scheduler: TaskScheduler | None = None


def get_scheduler() -> TaskScheduler:
    """Get or create global scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler


def start_scheduler() -> None:
    """Start the global scheduler."""
    scheduler = get_scheduler()
    scheduler.start()


def stop_scheduler() -> None:
    """Stop the global scheduler."""
    scheduler = get_scheduler()
    scheduler.stop()
