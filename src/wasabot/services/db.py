"""
SQLite database service with thread-safe connection pooling.

🐍 PYTHON NATIVE: Uses threading.local() for per-thread connections, built-in sqlite3
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wasabot.config import get_settings
from wasabot.services.logger import get_logger

logger = get_logger(__name__)


class DatabasePool:
    """
    Thread-safe SQLite connection pool using threading.local().
    
    🐍 PYTHON NATIVE: Each thread gets its own connection via threading.local()
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self._ensure_db_dir()

    def _ensure_db_dir(self) -> None:
        """Ensure database directory exists."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create connection for current thread."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            with self._lock:
                conn = sqlite3.connect(
                    str(self._db_path),
                    check_same_thread=False,  # We manage thread safety ourselves
                    isolation_level=None,  # Autocommit mode for explicit transactions
                )
                conn.row_factory = sqlite3.Row  # Enable dict-like access
                # Enable foreign keys and WAL mode for better concurrency
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA journal_mode = WAL")
                self._local.connection = conn
                logger.info(f"database_connection_created | path={self._db_path}")
        return self._local.connection

    def close_all(self) -> None:
        """Close all connections (for shutdown)."""
        if hasattr(self._local, "connection") and self._local.connection is not None:
            self._local.connection.close()
            self._local.connection = None
            logger.info("database_connection_closed")

    @property
    def connection(self) -> sqlite3.Connection:
        """Get current thread's connection."""
        return self._get_connection()


# Global database pool instance (initialized on first use)
_db_pool: DatabasePool | None = None
_init_lock = threading.Lock()


def get_db_pool() -> DatabasePool:
    """Get or create global database pool."""
    global _db_pool
    if _db_pool is None:
        with _init_lock:
            if _db_pool is None:
                settings = get_settings()
                _db_pool = DatabasePool(settings.absolute_db_path)
                _init_tables(_db_pool)
    return _db_pool


def _init_tables(pool: DatabasePool) -> None:
    """Initialize database tables if they don't exist."""
    conn = pool.connection
    cursor = conn.cursor()

    # Profiles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            wa_id TEXT PRIMARY KEY,
            name TEXT,
            traits JSON,
            topics JSON,
            notes TEXT,
            status TEXT,
            last_active INTEGER
        )
    """)

    # Conversations table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wa_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            FOREIGN KEY (wa_id) REFERENCES profiles(wa_id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_wa_id ON conversations(wa_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp)")

    # Scheduled tasks table - extended with action, video_url, caption for delayed videos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_tasks (
            task_id TEXT PRIMARY KEY,
            wa_id TEXT NOT NULL,
            message TEXT NOT NULL,
            execute_at INTEGER NOT NULL,
            correlation_id TEXT,
            is_group INTEGER DEFAULT 0,
            action TEXT DEFAULT 'send_message',
            video_url TEXT,
            caption TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_execute_at ON scheduled_tasks(execute_at)")

    conn.commit()
    logger.info("database_tables_initialized")


# ──────────────────────────────────────────────────────────────
# Profile CRUD Operations
# ──────────────────────────────────────────────────────────────


def save_profile(
    wa_id: str,
    name: str | None = None,
    traits: dict[str, Any] | None = None,
    topics: list[str] | None = None,
    notes: str | None = None,
    status: str | None = None,
) -> None:
    """Save or update user profile."""
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO profiles (wa_id, name, traits, topics, notes, status, last_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(wa_id) DO UPDATE SET
            name = COALESCE(excluded.name, profiles.name),
            traits = COALESCE(excluded.traits, profiles.traits),
            topics = COALESCE(excluded.topics, profiles.topics),
            notes = COALESCE(excluded.notes, profiles.notes),
            status = COALESCE(excluded.status, profiles.status),
            last_active = excluded.last_active
    """, (
        wa_id,
        name,
        json.dumps(traits) if traits else None,
        json.dumps(topics) if topics else None,
        notes,
        status,
        int(datetime.now(timezone.utc).timestamp()),
    ))

    conn.commit()
    logger.info(f"profile_saved | wa_id={wa_id}")


def load_profile(wa_id: str) -> dict[str, Any] | None:
    """Load user profile by WhatsApp ID."""
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM profiles WHERE wa_id = ?", (wa_id,))
    row = cursor.fetchone()

    if row is None:
        return None

    # Convert Row to dict and parse JSON fields
    profile = dict(row)
    if profile.get("traits"):
        profile["traits"] = json.loads(profile["traits"])
    if profile.get("topics"):
        profile["topics"] = json.loads(profile["topics"])

    return profile


def profile_exists(wa_id: str) -> bool:
    """Check if profile exists."""
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM profiles WHERE wa_id = ? LIMIT 1", (wa_id,))
    return cursor.fetchone() is not None


# ──────────────────────────────────────────────────────────────
# Conversation CRUD Operations
# ──────────────────────────────────────────────────────────────


def add_conversation(wa_id: str, role: str, content: str) -> None:
    """Add a conversation message to history."""
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    # Ensure profile exists first (foreign key requirement)
    if not profile_exists(wa_id):
        save_profile(wa_id=wa_id)

    timestamp = int(datetime.now(timezone.utc).timestamp())

    cursor.execute("""
        INSERT INTO conversations (wa_id, role, content, timestamp)
        VALUES (?, ?, ?, ?)
    """, (wa_id, role, content, timestamp))

    conn.commit()
    logger.debug(f"conversation_added | wa_id={wa_id} | role={role}")


def load_conversation(wa_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Load conversation history for a user."""
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    cursor.execute("""
        SELECT role, content, timestamp
        FROM conversations
        WHERE wa_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (wa_id, limit))

    rows = cursor.fetchall()
    # Return in chronological order (oldest first)
    return [dict(row) for row in reversed(rows)]


def clear_conversation(wa_id: str) -> None:
    """Clear conversation history for a user."""
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    cursor.execute("DELETE FROM conversations WHERE wa_id = ?", (wa_id,))
    conn.commit()
    logger.info(f"conversation_cleared | wa_id={wa_id}")


# ──────────────────────────────────────────────────────────────
# Scheduled Tasks CRUD Operations
# ──────────────────────────────────────────────────────────────


def add_task(
    task_id: str,
    wa_id: str,
    message: str,
    execute_at: int,
    correlation_id: str | None = None,
    is_group: bool = False,
    action: str = "send_message",
    video_url: str | None = None,
    caption: str | None = None,
) -> None:
    """
    Add a scheduled task.
    
    Args:
        task_id: Unique task identifier
        wa_id: Recipient WhatsApp ID
        message: Message text (for send_message action)
        execute_at: Unix timestamp for execution
        correlation_id: Correlation ID for tracing
        is_group: Whether this is a group message
        action: Task action type ('send_message' or 'send_video')
        video_url: URL of video to send (for send_video action)
        caption: Caption for video (for send_video action)
    """
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO scheduled_tasks (task_id, wa_id, message, execute_at, correlation_id, is_group, action, video_url, caption)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (task_id, wa_id, message, execute_at, correlation_id, 1 if is_group else 0, action, video_url, caption))

    conn.commit()
    logger.info(f"task_scheduled | task_id={task_id} | execute_at={execute_at} | action={action}")


def get_due_tasks(current_time: int | None = None) -> list[dict[str, Any]]:
    """Get all tasks that are due for execution."""
    if current_time is None:
        current_time = int(datetime.now(timezone.utc).timestamp())

    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    # 🎬 DELAYED VIDEO: Include action, video_url, caption in task retrieval
    cursor.execute("""
        SELECT task_id, wa_id, message, execute_at, correlation_id, is_group, action, video_url, caption
        FROM scheduled_tasks
        WHERE execute_at <= ?
        ORDER BY execute_at ASC
    """, (current_time,))

    rows = cursor.fetchall()
    tasks = []
    for row in rows:
        task = dict(row)
        task["is_group"] = bool(task["is_group"])
        tasks.append(task)

    if tasks:
        logger.info(f"due_tasks_found | count={len(tasks)}")
    return tasks


def delete_task(task_id: str) -> None:
    """Delete a scheduled task."""
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    cursor.execute("DELETE FROM scheduled_tasks WHERE task_id = ?", (task_id,))
    conn.commit()
    logger.debug(f"task_deleted | task_id={task_id}")


def get_task(task_id: str) -> dict[str, Any] | None:
    """Get a specific task by ID."""
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    cursor.execute("""
        SELECT task_id, wa_id, message, execute_at, correlation_id, is_group
        FROM scheduled_tasks
        WHERE task_id = ?
    """, (task_id,))

    row = cursor.fetchone()
    if row is None:
        return None

    task = dict(row)
    task["is_group"] = bool(task["is_group"])
    return task
