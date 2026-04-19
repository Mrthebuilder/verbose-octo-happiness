"""Append-only, hash-chained audit log.

Every entry stores the SHA-256 of the previous entry, so any silent
tampering with the log (inserting, deleting, or modifying an entry)
breaks the chain and is detectable by :meth:`AuditLog.verify`.

This is not a replacement for a real SIEM. It exists so the user can
scroll back and see *exactly* why the assistant said what it said, and
so a compromised process can't quietly rewrite that history.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class AuditEntry:
    """A single audit record."""

    timestamp: float
    kind: str  # e.g. "recommendation", "security.integrity_check", "refusal"
    user_id: str
    payload: dict
    prev_hash: str
    entry_hash: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)


def _compute_hash(
    timestamp: float, kind: str, user_id: str, payload: dict, prev_hash: str
) -> str:
    body = json.dumps(
        {
            "timestamp": timestamp,
            "kind": kind,
            "user_id": user_id,
            "payload": payload,
            "prev_hash": prev_hash,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class AuditLog:
    """Hash-chained JSONL log at ``<root>/audit.jsonl``."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)
        self.path = self.root / "audit.jsonl"

    def _last_hash(self) -> str:
        if not self.path.exists():
            return GENESIS_HASH
        last: str | None = None
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    last = line
        if last is None:
            return GENESIS_HASH
        return json.loads(last)["entry_hash"]

    def append(
        self,
        kind: str,
        user_id: str,
        payload: dict,
        timestamp: float | None = None,
    ) -> AuditEntry:
        """Append an entry and return it."""
        self.root.mkdir(parents=True, exist_ok=True)
        ts = time.time() if timestamp is None else timestamp
        prev = self._last_hash()
        entry_hash = _compute_hash(ts, kind, user_id, payload, prev)
        entry = AuditEntry(
            timestamp=ts,
            kind=kind,
            user_id=user_id,
            payload=payload,
            prev_hash=prev,
            entry_hash=entry_hash,
        )
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(entry.to_json() + "\n")
        return entry

    def load(self) -> list[AuditEntry]:
        """Return every entry in order."""
        if not self.path.exists():
            return []
        entries: list[AuditEntry] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                entries.append(AuditEntry(**data))
        return entries

    def verify(self) -> bool:
        """Return True iff every entry's hash chain matches."""
        prev = GENESIS_HASH
        for entry in self.load():
            if entry.prev_hash != prev:
                return False
            expected = _compute_hash(
                entry.timestamp,
                entry.kind,
                entry.user_id,
                entry.payload,
                entry.prev_hash,
            )
            if expected != entry.entry_hash:
                return False
            prev = entry.entry_hash
        return True


__all__ = ["AuditEntry", "AuditLog", "GENESIS_HASH"]
