from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from software.assistant import (
    SYSTEM_PROMPT,
    AssistantReply,
    MiningAssistant,
    MockBackend,
    default_backend,
)
from software.optimizer import ProfitabilityOptimizer
from software.profile import UserProfile
from software.profitability import Coin, Rig


@pytest.fixture
def rig() -> Rig:
    return Rig(hashrate_hs=100e12, power_watts=3250)


@pytest.fixture
def coins() -> list[Coin]:
    return [
        Coin(
            symbol="BTC",
            price_usd=60_000.0,
            network_hashrate_hs=500e18,
            block_reward=3.125,
            block_time_seconds=600.0,
        ),
        Coin(
            symbol="LTC",
            price_usd=80.0,
            network_hashrate_hs=800e12,
            block_reward=6.25,
            block_time_seconds=150.0,
        ),
    ]


def test_ask_returns_assistant_reply_with_payload(
    tmp_path: Path, rig: Rig, coins: list[Coin]
) -> None:
    assistant = MiningAssistant(
        optimizer=ProfitabilityOptimizer(),
        backend=MockBackend(),
        data_dir=tmp_path,
    )
    reply = assistant.ask("alice", "What should I mine?", rig, coins, 0.10)
    assert isinstance(reply, AssistantReply)
    assert not reply.refused
    optimizer_top = ProfitabilityOptimizer().best(rig, coins, 0.10).symbol
    assert optimizer_top in reply.answer
    assert reply.payload["rankings"][0]["symbol"] == optimizer_top


@dataclass
class RecordingBackend:
    system: str = ""
    user: str = ""

    def complete(self, system: str, user: str) -> str:
        self.system = system
        self.user = user
        return "ok"


def test_prompt_contains_persona_profile_and_ranking_context(
    tmp_path: Path, rig: Rig, coins: list[Coin]
) -> None:
    backend = RecordingBackend()
    assistant = MiningAssistant(backend=backend, data_dir=tmp_path)
    assistant.profiles.save(
        UserProfile(user_id="alice", display_name="Alice", stated_goal="vacation")
    )
    assistant.ask("alice", "best coin?", rig, coins, 0.10)
    assert backend.system == SYSTEM_PROMPT
    assert "rankings" in backend.user
    assert "best coin?" in backend.user
    assert "Alice" in backend.user
    assert "vacation" in backend.user


def test_persona_refusal_short_circuits_backend(
    tmp_path: Path, rig: Rig, coins: list[Coin]
) -> None:
    backend = RecordingBackend()
    assistant = MiningAssistant(backend=backend, data_dir=tmp_path)
    reply = assistant.ask(
        "alice",
        "Should I use my kids' college fund to mine?",
        rig,
        coins,
        0.10,
    )
    assert reply.refused
    assert backend.system == ""  # backend never called
    assert "advisor" in reply.answer.lower()


def test_memory_persists_across_calls(
    tmp_path: Path, rig: Rig, coins: list[Coin]
) -> None:
    assistant = MiningAssistant(backend=MockBackend(), data_dir=tmp_path)
    assistant.ask("alice", "first question", rig, coins, 0.10)
    assistant.ask("alice", "second question", rig, coins, 0.10)
    memory = assistant._memory("alice")
    messages = memory.load()
    # 2 user turns + 2 assistant turns
    assert len(messages) == 4
    assert messages[0].content == "first question"
    assert messages[2].content == "second question"


def test_audit_log_records_recommendation_and_verifies(
    tmp_path: Path, rig: Rig, coins: list[Coin]
) -> None:
    assistant = MiningAssistant(backend=MockBackend(), data_dir=tmp_path)
    assistant.ask("alice", "which coin?", rig, coins, 0.10)
    entries = assistant.audit.load()
    assert len(entries) == 1
    assert entries[0].kind == "recommendation"
    assert entries[0].user_id == "alice"
    assert "rankings" in entries[0].payload
    assert assistant.audit.verify()


def test_audit_log_records_refusal(
    tmp_path: Path, rig: Rig, coins: list[Coin]
) -> None:
    assistant = MiningAssistant(backend=MockBackend(), data_dir=tmp_path)
    assistant.ask(
        "alice",
        "should I put my retirement into mining?",
        rig,
        coins,
        0.10,
    )
    entries = assistant.audit.load()
    assert len(entries) == 1
    assert entries[0].kind == "refusal"


def test_default_backend_without_keys_is_mock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert isinstance(default_backend(), MockBackend)
