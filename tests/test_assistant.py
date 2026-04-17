from __future__ import annotations

from dataclasses import dataclass

import pytest

from software.assistant import (
    SYSTEM_PROMPT,
    MiningAssistant,
    MockBackend,
    default_backend,
)
from software.optimizer import ProfitabilityOptimizer
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


def test_mock_backend_recommends_top_ranked_coin(
    rig: Rig, coins: list[Coin]
) -> None:
    assistant = MiningAssistant(
        optimizer=ProfitabilityOptimizer(), backend=MockBackend()
    )
    answer = assistant.ask("What should I mine?", rig, coins, 0.10)
    optimizer_top = ProfitabilityOptimizer().best(rig, coins, 0.10).symbol
    assert optimizer_top in answer


@dataclass
class RecordingBackend:
    system: str = ""
    user: str = ""

    def complete(self, system: str, user: str) -> str:
        self.system = system
        self.user = user
        return "ok"


def test_prompt_contains_system_and_ranking_context(
    rig: Rig, coins: list[Coin]
) -> None:
    backend = RecordingBackend()
    assistant = MiningAssistant(backend=backend)
    assistant.ask("best coin?", rig, coins, 0.10)
    assert backend.system == SYSTEM_PROMPT
    assert "rankings" in backend.user
    assert "best coin?" in backend.user


def test_default_backend_without_keys_is_mock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert isinstance(default_backend(), MockBackend)
