"""SQLite-backed conversation history with token-aware truncation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Optional

import aiosqlite
import tiktoken

from utils.config import Settings, get_settings
from utils.logger import get_logger

logger = get_logger(__name__)

Role = Literal["system", "user", "assistant"]


@dataclass
class MessageRecord:
    """Single stored message."""

    role: Role
    content: str
    timestamp: str
    truncated_to_8k: bool = False


class ContextStore:
    """Async SQLite store for per-user dialogue history."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.db_path = self.settings.context_db_path
        self._encoding = tiktoken.get_encoding("cl100k_base")
        self._initialized = False

    async def initialize(self) -> None:
        """Create database schema if needed."""
        if self._initialized:
            return

        self.settings.db_dir.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS user_modes (
                    user_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL DEFAULT 'text',
                    updated_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    truncated_to_8k INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)"
            )
            await db.commit()

        self._initialized = True
        logger.info("Context store initialized at %s", self.db_path)

    async def get_mode(self, user_id: str) -> str:
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT mode FROM user_modes WHERE user_id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()
            return row[0] if row else "text"

    async def set_mode(self, user_id: str, mode: str) -> None:
        await self.initialize()
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO user_modes (user_id, mode, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    mode = excluded.mode,
                    updated_at = excluded.updated_at
                """,
                (user_id, mode, now),
            )
            await db.commit()
        logger.debug("User %s mode set to %s", user_id, mode)

    async def add_message(
        self,
        user_id: str,
        role: Role,
        content: str,
        *,
        truncated_to_8k: bool = False,
    ) -> None:
        """Persist a message and enforce token limits."""
        await self.initialize()
        timestamp = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO messages (user_id, role, content, timestamp, truncated_to_8k)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, role, content, timestamp, int(truncated_to_8k)),
            )
            await db.commit()

        await self._truncate_if_needed(user_id)

    async def get_history(
        self,
        user_id: str,
        *,
        include_system: bool = False,
    ) -> list[dict[str, str]]:
        """Return OpenAI-compatible message list for the user."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT role, content FROM messages
                WHERE user_id = ?
                ORDER BY id ASC
                """,
                (user_id,),
            )
            rows = await cursor.fetchall()

        history: list[dict[str, str]] = []
        for role, content in rows:
            if role == "system" and not include_system:
                continue
            history.append({"role": role, "content": content})
        return history

    async def reset(self, user_id: str) -> None:
        """Clear all messages for a user."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
            await db.commit()
        logger.info("Context reset for user %s", user_id)

    async def export_user_context(self, user_id: str) -> list[MessageRecord]:
        """Export full message records (for debugging / stats)."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT role, content, timestamp, truncated_to_8k
                FROM messages
                WHERE user_id = ?
                ORDER BY id ASC
                """,
                (user_id,),
            )
            rows = await cursor.fetchall()

        return [
            MessageRecord(
                role=row[0],
                content=row[1],
                timestamp=row[2],
                truncated_to_8k=bool(row[3]),
            )
            for row in rows
        ]

    def count_tokens(self, text: str) -> int:
        return len(self._encoding.encode(text))

    def count_messages_tokens(self, messages: list[dict[str, str]]) -> int:
        total = 0
        for msg in messages:
            total += self.count_tokens(msg.get("content", ""))
            total += 4  # rough per-message overhead
        return total

    async def _truncate_if_needed(self, user_id: str) -> None:
        """Drop oldest messages when token or count limits are exceeded."""
        history = await self.get_history(user_id, include_system=True)
        if not history:
            return

        total_tokens = self.count_messages_tokens(history)
        max_tokens = self.settings.max_context_tokens
        max_messages = self.settings.max_history_messages

        if total_tokens <= max_tokens and len(history) <= max_messages:
            return

        async with aiosqlite.connect(self.db_path) as db:
            while history and (
                self.count_messages_tokens(history) > max_tokens
                or len(history) > max_messages
            ):
                history.pop(0)
                await db.execute(
                    """
                    DELETE FROM messages
                    WHERE id = (
                        SELECT id FROM messages
                        WHERE user_id = ?
                        ORDER BY id ASC
                        LIMIT 1
                    )
                    """,
                    (user_id,),
                )

            await db.execute(
                """
                UPDATE messages
                SET truncated_to_8k = 1
                WHERE user_id = ?
                """,
                (user_id,),
            )
            await db.commit()

        logger.info(
            "Truncated context for user %s to %d messages (~%d tokens)",
            user_id,
            len(history),
            self.count_messages_tokens(history),
        )

    async def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about stored contexts."""
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(DISTINCT user_id) FROM messages")
            users_row = await cursor.fetchone()
            cursor = await db.execute("SELECT COUNT(*) FROM messages")
            messages_row = await cursor.fetchone()

        return {
            "users_with_messages": users_row[0] if users_row else 0,
            "total_messages": messages_row[0] if messages_row else 0,
            "db_path": str(self.db_path),
        }
