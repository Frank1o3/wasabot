"""
SQLite database service with thread-safe connection pooling.

🐍 PYTHON NATIVE: Uses threading.local() for per-thread connections, built-in sqlite3
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
import threading
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

    # 👥 SOCIAL GRAPH: Relationships table to track who knows whom
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS relationships (
            user_wa_id TEXT NOT NULL,
            known_person_wa_id TEXT,
            known_person_name TEXT NOT NULL,
            context TEXT,
            last_mentioned INTEGER,
            PRIMARY KEY (user_wa_id, known_person_name),
            FOREIGN KEY (user_wa_id) REFERENCES profiles(wa_id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_user ON relationships(user_wa_id)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_relationships_person ON relationships(known_person_name)"
    )

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
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp)"
    )

    # Scheduled tasks table - extended with action, video_url, caption for delayed videos
    # 👤 HUMANITY FEATURE: Added reply_to_message_id for contextual replies
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
            caption TEXT,
            reply_to_message_id TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_execute_at ON scheduled_tasks(execute_at)")

    # 🎬 DELAYED VIDEO + 👤 HUMANITY FEATURE: Add new columns to existing tables if they don't exist
    try:  # noqa: SIM105
        cursor.execute("ALTER TABLE scheduled_tasks ADD COLUMN action TEXT DEFAULT 'send_message'")
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:  # noqa: SIM105
        cursor.execute("ALTER TABLE scheduled_tasks ADD COLUMN video_url TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:  # noqa: SIM105
        cursor.execute("ALTER TABLE scheduled_tasks ADD COLUMN caption TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:  # noqa: SIM105
        cursor.execute("ALTER TABLE scheduled_tasks ADD COLUMN reply_to_message_id TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

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

    cursor.execute(
        """
        INSERT INTO profiles (wa_id, name, traits, topics, notes, status, last_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(wa_id) DO UPDATE SET
            name = COALESCE(excluded.name, profiles.name),
            traits = COALESCE(excluded.traits, profiles.traits),
            topics = COALESCE(excluded.topics, profiles.topics),
            notes = COALESCE(excluded.notes, profiles.notes),
            status = COALESCE(excluded.status, profiles.status),
            last_active = excluded.last_active
    """,
        (
            wa_id,
            name,
            json.dumps(traits) if traits else None,
            json.dumps(topics) if topics else None,
            notes,
            status,
            int(datetime.now(UTC).timestamp()),
        ),
    )

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

    timestamp = int(datetime.now(UTC).timestamp())

    cursor.execute(
        """
        INSERT INTO conversations (wa_id, role, content, timestamp)
        VALUES (?, ?, ?, ?)
    """,
        (wa_id, role, content, timestamp),
    )

    conn.commit()
    logger.debug(f"conversation_added | wa_id={wa_id} | role={role}")


def load_conversation(wa_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Load conversation history for a user."""
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT role, content, timestamp
        FROM conversations
        WHERE wa_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """,
        (wa_id, limit),
    )

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


def clear_all_conversations() -> None:
    """Clear all conversation history for all users."""
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    cursor.execute("DELETE FROM conversations")
    conn.commit()
    logger.info("all_conversations_cleared")


def clear_all_tasks() -> None:
    """Clear all scheduled tasks."""
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    cursor.execute("DELETE FROM scheduled_tasks")
    conn.commit()
    logger.info("all_tasks_cleared")


def delete_profile_and_conversations(wa_id: str) -> None:
    """Delete a user profile and all associated conversations."""
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    # Delete conversations first (foreign key constraint)
    cursor.execute("DELETE FROM conversations WHERE wa_id = ?", (wa_id,))
    # Then delete the profile
    cursor.execute("DELETE FROM profiles WHERE wa_id = ?", (wa_id,))
    conn.commit()
    logger.info(f"profile_and_conversations_deleted | wa_id={wa_id}")


def search_profiles_by_name(name_query: str) -> list[dict[str, Any]]:
    """Search for profiles by name (case-insensitive partial match)."""
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    cursor.execute(
        "SELECT wa_id, name, traits, topics, notes FROM profiles WHERE LOWER(name) LIKE LOWER(?)",
        (f"%{name_query}%",),
    )

    rows = cursor.fetchall()
    results = []
    for row in rows:
        profile = dict(row)
        if profile.get("traits"):
            profile["traits"] = json.loads(profile["traits"])
        if profile.get("topics"):
            profile["topics"] = json.loads(profile["topics"])
        results.append(profile)

    return results


def find_conversations_about_person(person_name: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Find conversations that mention a specific person's name.
    Returns recent conversations where the person's name appears.
    """
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    # Search for conversations containing the person's name
    cursor.execute(
        """
        SELECT c.wa_id, c.role, c.content, c.timestamp, p.name as user_name
        FROM conversations c
        LEFT JOIN profiles p ON c.wa_id = p.wa_id
        WHERE LOWER(c.content) LIKE LOWER(?)
        ORDER BY c.timestamp DESC
        LIMIT ?
    """,
        (f"%{person_name}%", limit),
    )

    rows = cursor.fetchall()
    results = []
    for row in rows:
        conversation = dict(row)
        results.append(conversation)

    return results


def get_profile_by_wa_id(wa_id: str) -> dict[str, Any] | None:
    """Get a profile by WhatsApp ID with parsed JSON fields."""
    profile = load_profile(wa_id)
    return profile


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
    reply_to_message_id: str | None = None,  # 👤 HUMANITY FEATURE: Contextual reply support
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
        reply_to_message_id: 👤 HUMANITY FEATURE: Message ID to quote (for contextual reply)
    """
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO scheduled_tasks (task_id, wa_id, message, execute_at, correlation_id, is_group, action, video_url, caption, reply_to_message_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            task_id,
            wa_id,
            message,
            execute_at,
            correlation_id,
            1 if is_group else 0,
            action,
            video_url,
            caption,
            reply_to_message_id,
        ),
    )

    conn.commit()
    logger.info(f"task_scheduled | task_id={task_id} | execute_at={execute_at} | action={action}")


def get_due_tasks(current_time: int | None = None) -> list[dict[str, Any]]:
    """Get all tasks that are due for execution."""
    if current_time is None:
        current_time = int(datetime.now(UTC).timestamp())

    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    # 🎬 DELAYED VIDEO + 👤 HUMANITY FEATURE: Include action, video_url, caption, reply_to_message_id in task retrieval
    cursor.execute(
        """
        SELECT task_id, wa_id, message, execute_at, correlation_id, is_group, action, video_url, caption, reply_to_message_id
        FROM scheduled_tasks
        WHERE execute_at <= ?
        ORDER BY execute_at ASC
    """,
        (current_time,),
    )

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

    cursor.execute(
        """
        SELECT task_id, wa_id, message, execute_at, correlation_id, is_group
        FROM scheduled_tasks
        WHERE task_id = ?
    """,
        (task_id,),
    )

    row = cursor.fetchone()
    if row is None:
        return None

    task = dict(row)
    task["is_group"] = bool(task["is_group"])
    return task


# ──────────────────────────────────────────────────────────────
# 👥 SOCIAL GRAPH: Relationship Management
# ──────────────────────────────────────────────────────────────


def add_relationship(
    user_wa_id: str,
    person_name: str,
    person_wa_id: str | None = None,
    context: str | None = None,
) -> None:
    """
    Record that a user knows/about a person.
    This builds a social graph allowing the AI to talk about people.

    Args:
        user_wa_id: WhatsApp ID of the user who knows this person
        person_name: Name of the person being known/mentioned
        person_wa_id: Optional WhatsApp ID if the person is also a bot user
        context: Context of how they know each other
    """
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    timestamp = int(datetime.now(UTC).timestamp())

    cursor.execute(
        """
        INSERT INTO relationships (user_wa_id, known_person_wa_id, known_person_name, context, last_mentioned)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_wa_id, known_person_name) DO UPDATE SET
            known_person_wa_id = COALESCE(excluded.known_person_wa_id, relationships.known_person_wa_id),
            context = COALESCE(excluded.context, relationships.context),
            last_mentioned = excluded.last_mentioned
    """,
        (user_wa_id, person_wa_id, person_name, context, timestamp),
    )

    conn.commit()
    logger.info(f"relationship_added | user={user_wa_id} | person={person_name}")


def get_relationships_for_user(user_wa_id: str) -> list[dict[str, Any]]:
    """
    Get all people that a user knows or has talked about.
    Returns list of relationship records with person info.
    """
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT r.user_wa_id, r.known_person_wa_id, r.known_person_name, r.context, r.last_mentioned,
               p.name as person_actual_name, p.topics as person_topics, p.notes as person_notes
        FROM relationships r
        LEFT JOIN profiles p ON r.known_person_wa_id = p.wa_id
        WHERE r.user_wa_id = ?
        ORDER BY r.last_mentioned DESC
    """,
        (user_wa_id,),
    )

    rows = cursor.fetchall()
    results = []
    for row in rows:
        rel = dict(row)
        if rel.get("person_topics"):
            rel["person_topics"] = json.loads(rel["person_topics"])
        results.append(rel)

    return results


def find_users_who_know_person(person_name: str) -> list[dict[str, Any]]:
    """
    Find all users who have mentioned or know a specific person.
    Useful for group conversations or when someone asks "quién conoce a Pablo?"
    """
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT r.user_wa_id, r.known_person_wa_id, r.context, r.last_mentioned,
               p.name as user_name, p.topics as user_topics
        FROM relationships r
        LEFT JOIN profiles p ON r.user_wa_id = p.wa_id
        WHERE LOWER(r.known_person_name) LIKE LOWER(?)
        ORDER BY r.last_mentioned DESC
    """,
        (f"%{person_name}%",),
    )

    rows = cursor.fetchall()
    results = []
    for row in rows:
        rel = dict(row)
        if rel.get("user_topics"):
            rel["user_topics"] = json.loads(rel["user_topics"])
        results.append(rel)

    return results


def search_people_in_network(name_query: str) -> list[dict[str, Any]]:
    """
    Search for people in the entire network by name.
    Returns both their profile info and who knows them.
    """
    pool = get_db_pool()
    conn = pool.connection
    cursor = conn.cursor()

    # First, try to find exact profile matches
    cursor.execute(
        """
        SELECT p.wa_id, p.name, p.traits, p.topics, p.notes,
               COUNT(DISTINCT r.user_wa_id) as known_by_count
        FROM profiles p
        LEFT JOIN relationships r ON p.wa_id = r.known_person_wa_id
        WHERE LOWER(p.name) LIKE LOWER(?)
        GROUP BY p.wa_id
        ORDER BY known_by_count DESC, p.last_active DESC
    """,
        (f"%{name_query}%",),
    )

    rows = cursor.fetchall()
    results = []
    for row in rows:
        profile = dict(row)
        if profile.get("traits"):
            profile["traits"] = json.loads(profile["traits"])
        if profile.get("topics"):
            profile["topics"] = json.loads(profile["topics"])
        results.append(profile)

    return results
