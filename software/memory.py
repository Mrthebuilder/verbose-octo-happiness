"""Per-user conversation memory persisted as JSONL on disk.

Design goals:
* Human-readable on disk so the user can always see what the assistant
  remembers about them.
* Append-only for conversation turns, so a compromised process cannot
  silently rewrite history.
* No network, no database — just a directory of JSONL files.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Message:
    """A single chat turn."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: float

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> Message:
        return cls(
            role=str(data["role"]),
            content=str(data["content"]),
            timestamp=float(data["timestamp"]),
        )


class ConversationMemory:
    """Load/append conversation history for a single user.

    Storage layout: ``<root>/<user_id>/conversation.jsonl``. Each line is
    one :class:`Message`.
    """

    def __init__(self, user_id: str, root: str | os.PathLike[str]) -> None:
        if not user_id or "/" in user_id or ".." in user_id:
            raise ValueError("user_id must be a simple identifier")
        self.user_id = user_id
        self.root = Path(root)
        self.user_dir = self.root / user_id
        self.path = self.user_dir / "conversation.jsonl"

    def _ensure_dir(self) -> None:
        self.user_dir.mkdir(parents=True, exist_ok=True)

    def append(self, role: str, content: str) -> Message:
        """Append a message to the on-disk log and return it."""
        if role not in ("user", "assistant"):
            raise ValueError("role must be 'user' or 'assistant'")
        self._ensure_dir()
        message = Message(role=role, content=content, timestamp=time.time())
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(message.to_json() + "\n")
        return message

    def load(self, limit: int | None = None) -> list[Message]:
        """Load all (or the most recent ``limit``) messages for this user."""
        if not self.path.exists():
            return []
        messages: list[Message] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                messages.append(Message.from_dict(json.loads(line)))
        if limit is not None and limit >= 0:
            return messages[-limit:]
        return messages

    def clear(self) -> None:
        """Delete this user's conversation log (explicit user action only)."""
        if self.path.exists():
            self.path.unlink()


__all__ = ["ConversationMemory", "Message"]
