from __future__ import annotations

from pathlib import Path

from software.audit import GENESIS_HASH, AuditLog


def test_first_entry_chains_to_genesis(tmp_path: Path) -> None:
    log = AuditLog(root=tmp_path)
    entry = log.append(
        kind="recommendation",
        user_id="alice",
        payload={"answer": "mine BTC"},
    )
    assert entry.prev_hash == GENESIS_HASH
    assert entry.entry_hash != GENESIS_HASH


def test_chain_verifies_over_many_entries(tmp_path: Path) -> None:
    log = AuditLog(root=tmp_path)
    for i in range(10):
        log.append(
            kind="recommendation",
            user_id="alice",
            payload={"i": i},
        )
    assert log.verify()


def test_tampering_breaks_chain(tmp_path: Path) -> None:
    log = AuditLog(root=tmp_path)
    log.append(kind="recommendation", user_id="alice", payload={"i": 0})
    log.append(kind="recommendation", user_id="alice", payload={"i": 1})
    log.append(kind="recommendation", user_id="alice", payload={"i": 2})
    assert log.verify()

    # Silently rewrite the middle entry's payload on disk and confirm
    # the chain no longer verifies.
    lines = log.path.read_text(encoding="utf-8").splitlines()
    tampered = lines[1].replace('"i": 1', '"i": 99')
    lines[1] = tampered
    log.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert not log.verify()


def test_empty_log_verifies(tmp_path: Path) -> None:
    assert AuditLog(root=tmp_path).verify()
