"""Short-term memory implementation for MemLite."""

from collections import deque
from dataclasses import dataclass

from memolite.storage.session_store import SqliteSessionStore


@dataclass(slots=True)
class ShortTermMessage:
    """A single message stored in short-term memory."""

    uid: str
    content: str
    producer_id: str
    producer_role: str
    created_at: str | None = None


class ShortTermMemory:
    """Manage a bounded working-memory window and summary."""

    def __init__(
        self,
        *,
        session_key: str,
        session_store: SqliteSessionStore,
        message_capacity: int = 4096,
        summary: str = "",
        messages: list[ShortTermMessage] | None = None,
    ) -> None:
        self._session_key = session_key
        self._session_store = session_store
        self._message_capacity = message_capacity
        self._summary = summary
        self._messages: deque[ShortTermMessage] = deque(messages or [])
        self._current_message_len = sum(len(message.content) for message in self._messages)
        self._closed = False

    @property
    def summary(self) -> str:
        """Return the current summary text."""
        return self._summary

    @property
    def message_capacity(self) -> int:
        """Return the configured memory capacity."""
        return self._message_capacity

    @property
    def current_message_length(self) -> int:
        """Return the total message characters currently buffered."""
        return self._current_message_len

    @classmethod
    async def create(
        cls,
        *,
        session_key: str,
        session_store: SqliteSessionStore,
        message_capacity: int = 4096,
    ) -> "ShortTermMemory":
        """Create an instance and restore persisted summary if present."""
        session = await session_store.get_session(session_key)
        summary = session.summary if session is not None else ""
        return cls(
            session_key=session_key,
            session_store=session_store,
            message_capacity=message_capacity,
            summary=summary,
        )

    async def add_messages(self, messages: list[ShortTermMessage]) -> bool:
        """Add messages and summarize if capacity is exceeded."""
        self._ensure_open()
        for message in messages:
            self._messages.append(message)
            self._current_message_len += len(message.content)
        if await self.is_overflowing():
            await self._summarize_overflow()
            return True
        return False

    async def delete_episode(self, uid: str) -> bool:
        """Delete a single buffered episode by uid."""
        self._ensure_open()
        remaining: deque[ShortTermMessage] = deque()
        deleted = False
        removed_length = 0
        for message in self._messages:
            if message.uid == uid and not deleted:
                deleted = True
                removed_length += len(message.content)
                continue
            remaining.append(message)
        self._messages = remaining
        self._current_message_len -= removed_length
        return deleted

    async def is_overflowing(self) -> bool:
        """Return whether current content exceeds capacity."""
        return self._current_message_len > self._message_capacity

    async def _summarize_overflow(self) -> None:
        """Create a deterministic summary from evicted messages."""
        evicted: list[ShortTermMessage] = []
        while self._messages and self._current_message_len > self._message_capacity:
            message = self._messages.popleft()
            self._current_message_len -= len(message.content)
            evicted.append(message)

        if not evicted:
            return

        summary_lines = [f"{message.producer_role}: {message.content}" for message in evicted]
        summary_chunk = " | ".join(summary_lines)
        self._summary = (
            f"{self._summary} || {summary_chunk}" if self._summary else summary_chunk
        )
        await self.persist_summary()

    async def persist_summary(self) -> None:
        """Persist the current summary to the session store."""
        self._ensure_open()
        await self._session_store.update_summary(self._session_key, self._summary)

    async def close(self) -> None:
        """Persist summary and reject future writes."""
        if self._closed:
            return
        await self.persist_summary()
        self._closed = True

    async def reset(self) -> None:
        """Clear messages and summary, persisting the cleared summary."""
        self._messages.clear()
        self._current_message_len = 0
        self._summary = ""
        self._closed = False
        await self.persist_summary()

    def get_messages(self) -> list[ShortTermMessage]:
        """Return the buffered short-term messages."""
        return list(self._messages)

    def get_context(self) -> str:
        """Return a plain-text context string using summary and messages."""
        parts: list[str] = []
        if self._summary:
            parts.append(f"Summary: {self._summary}")
        if self._messages:
            parts.extend(
                f"{message.producer_role}: {message.content}" for message in self._messages
            )
        return "\n".join(parts)

    async def restore_summary(self) -> str:
        """Reload summary from the session store."""
        session = await self._session_store.get_session(self._session_key)
        self._summary = session.summary if session is not None else ""
        return self._summary

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("ShortTermMemory is closed")
