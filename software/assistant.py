"""LLM-backed mining assistant with a pluggable backend.

The assistant exposes a small ``ask`` API that composes a prompt from a
rig description, an electricity cost, and a slate of candidate coins,
then delegates the natural-language answer to a :class:`LLMBackend`.

Three backends are provided:

* :class:`MockBackend` — deterministic, no network. Used by tests and as
  the default when no API key is configured.
* :class:`OpenAIBackend` — uses the ``openai`` package. Activated when
  ``OPENAI_API_KEY`` is set in the environment.
* :class:`AnthropicBackend` — uses the ``anthropic`` package. Activated
  when ``ANTHROPIC_API_KEY`` is set in the environment.

The backends are intentionally thin; we don't do function/tool calling
here so the assistant stays usable even without paid API access. The
optimizer is run locally and its output is injected into the prompt as
structured context.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from .optimizer import ProfitabilityOptimizer, Ranking
from .profitability import Coin, Rig

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a cryptocurrency mining profitability assistant. "
    "Answer concisely and base your recommendation on the structured "
    "context provided. Do not invent numbers that are not in the context."
)


class LLMBackend(Protocol):
    """Minimal interface every backend must implement."""

    def complete(self, system: str, user: str) -> str:  # pragma: no cover
        ...


@dataclass
class MockBackend:
    """Deterministic backend that does not call any network service.

    Produces a short, structured answer based purely on the ranking
    already computed locally. Suitable for tests and offline demos.
    """

    def complete(self, system: str, user: str) -> str:
        # Echo the first ranked coin back to the caller in a readable form.
        # The caller embeds the JSON ranking in ``user``; we parse it out.
        try:
            payload_start = user.index("{")
            payload = json.loads(user[payload_start:])
            top = payload["rankings"][0]
            return (
                f"Based on the numbers provided, mine {top['symbol']}: "
                f"predicted profit ${top['predicted_profit_per_day']:.2f}/day "
                f"(analytic ${top['analytic_profit_per_day']:.2f}/day)."
            )
        except (ValueError, KeyError, IndexError, json.JSONDecodeError):
            return "No ranking data available."


@dataclass
class OpenAIBackend:
    """Backend that delegates to OpenAI's chat completions API."""

    model: str = "gpt-4o-mini"
    api_key: str | None = None

    def complete(self, system: str, user: str) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - import guard
            raise RuntimeError(
                "openai package not installed; run `pip install openai`"
            ) from exc

        client = OpenAI(api_key=self.api_key or os.environ.get("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""


@dataclass
class AnthropicBackend:
    """Backend that delegates to Anthropic's messages API."""

    model: str = "claude-3-5-sonnet-latest"
    api_key: str | None = None
    max_tokens: int = 512

    def complete(self, system: str, user: str) -> str:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - import guard
            raise RuntimeError(
                "anthropic package not installed; run `pip install anthropic`"
            ) from exc

        client = anthropic.Anthropic(
            api_key=self.api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(
            block.text for block in response.content if getattr(block, "text", None)
        )


def default_backend() -> LLMBackend:
    """Pick a backend based on which API keys are set in the environment."""
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAIBackend()
    if os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicBackend()
    return MockBackend()


def _rankings_to_payload(
    rig: Rig,
    electricity_cost_per_kwh: float,
    rankings: list[Ranking],
) -> dict:
    return {
        "rig": {
            "hashrate_hs": rig.hashrate_hs,
            "power_watts": rig.power_watts,
        },
        "electricity_cost_per_kwh": electricity_cost_per_kwh,
        "rankings": [
            {
                "symbol": r.symbol,
                "predicted_profit_per_day": r.predicted_profit_per_day,
                "analytic_profit_per_day": r.analytic_profit_per_day,
            }
            for r in rankings
        ],
    }


class MiningAssistant:
    """High-level entry point for natural-language mining advice."""

    def __init__(
        self,
        optimizer: ProfitabilityOptimizer | None = None,
        backend: LLMBackend | None = None,
    ) -> None:
        self.optimizer = optimizer or ProfitabilityOptimizer()
        self.backend = backend or default_backend()

    def ask(
        self,
        question: str,
        rig: Rig,
        coins: Iterable[Coin],
        electricity_cost_per_kwh: float,
    ) -> str:
        """Answer ``question`` using the optimizer's ranking as context."""
        rankings = self.optimizer.rank(rig, coins, electricity_cost_per_kwh)
        payload = _rankings_to_payload(rig, electricity_cost_per_kwh, rankings)
        user_message = (
            f"Question: {question}\n\n"
            f"Context (JSON):\n{json.dumps(payload, indent=2)}"
        )
        logger.debug("Dispatching to %s", type(self.backend).__name__)
        return self.backend.complete(SYSTEM_PROMPT, user_message)


__all__ = [
    "AnthropicBackend",
    "LLMBackend",
    "MiningAssistant",
    "MockBackend",
    "OpenAIBackend",
    "SYSTEM_PROMPT",
    "default_backend",
]
