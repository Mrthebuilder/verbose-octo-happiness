from __future__ import annotations

from pathlib import Path

import pytest

from software.memory import ConversationMemory


def test_append_and_load_roundtrip(tmp_path: Path) -> None:
    memory = ConversationMemory(user_id="alice", root=tmp_path)
    memory.append("user", "hello")
    memory.append("assistant", "hi alice")
    messages = memory.load()
    assert [m.role for m in messages] == ["user", "assistant"]
    assert [m.content for m in messages] == ["hello", "hi alice"]


def test_load_limit_returns_most_recent(tmp_path: Path) -> None:
    memory = ConversationMemory(user_id="alice", root=tmp_path)
    for i in range(5):
        memory.append("user", f"q{i}")
    messages = memory.load(limit=2)
    assert [m.content for m in messages] == ["q3", "q4"]


def test_load_limit_zero_returns_empty_list(tmp_path: Path) -> None:
    # Regression: ``messages[-0:]`` returns the full list in Python,
    # so ``load(limit=0)`` must be special-cased to return [].
    memory = ConversationMemory(user_id="alice", root=tmp_path)
    for i in range(3):
        memory.append("user", f"q{i}")
    assert memory.load(limit=0) == []


def test_load_limit_none_returns_all(tmp_path: Path) -> None:
    memory = ConversationMemory(user_id="alice", root=tmp_path)
    for i in range(3):
        memory.append("user", f"q{i}")
    assert [m.content for m in memory.load()] == ["q0", "q1", "q2"]
    assert [m.content for m in memory.load(limit=None)] == ["q0", "q1", "q2"]


def test_clear_removes_file(tmp_path: Path) -> None:
    memory = ConversationMemory(user_id="alice", root=tmp_path)
    memory.append("user", "hello")
    assert memory.path.exists()
    memory.clear()
    assert not memory.path.exists()
    assert memory.load() == []


@pytest.mark.parametrize("bad_id", ["", "../escape", "a/b"])
def test_invalid_user_ids_rejected(tmp_path: Path, bad_id: str) -> None:
    with pytest.raises(ValueError):
        ConversationMemory(user_id=bad_id, root=tmp_path)


def test_invalid_role_rejected(tmp_path: Path) -> None:
    memory = ConversationMemory(user_id="alice", root=tmp_path)
    with pytest.raises(ValueError):
        memory.append("system", "oops")
