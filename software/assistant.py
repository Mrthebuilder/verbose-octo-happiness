"""LLM-backed mining assistant with a pluggable backend.

The assistant exposes an ``ask`` API that composes a prompt from the
user's profile, their prior conversation, their rig + electricity cost,
and a slate of candidate coins, then delegates the natural-language
answer to a :class:`LLMBackend`. Every recommendation is written to a
hash-chained audit log so the user can see exactly which numbers drove
it.

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
from pathlib import Path
from typing import Protocol

from .audit import AuditLog
from .memory import ConversationMemory, Message
from .optimizer import ProfitabilityOptimizer, Ranking
from .persona import Persona, default_persona, refusal_response, should_refuse
from .profile import ProfileStore, UserProfile
from .profitability import Coin, Rig

logger = logging.getLogger(__name__)

# Legacy constant kept for backward compatibility with earlier tests.
SYSTEM_PROMPT = default_persona().system_prompt


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
                "price_usd": r.coin.price_usd,
                "predicted_profit_per_day": r.predicted_profit_per_day,
                "analytic_profit_per_day": r.analytic_profit_per_day,
            }
            for r in rankings
        ],
    }


@dataclass
class AssistantReply:
    """Structured result of a single turn.

    Attributes:
        answer: The natural-language answer returned to the user.
        refused: True if the persona's hard-refusal rules fired and the
            answer is a canned refusal (LLM was not called).
        payload: The structured ranking/profile context that was passed
            to the LLM. Exposed so callers can show the user the exact
            numbers the answer was based on.
    """

    answer: str
    refused: bool
    payload: dict


class MiningAssistant:
    """High-level entry point for natural-language mining advice.

    Parameters
    ----------
    optimizer:
        A :class:`ProfitabilityOptimizer`. Defaults to an untrained one
        that uses the analytic profit formula.
    backend:
        An :class:`LLMBackend` implementation. Defaults to whichever of
        OpenAI/Anthropic has an API key set, falling back to
        :class:`MockBackend`.
    persona:
        The :class:`Persona` that governs the assistant's system prompt
        and refusal topics. Defaults to the "Brick" persona.
    data_dir:
        Directory under which per-user profiles, conversation memory,
        and the audit log are stored. Defaults to ``./data`` relative to
        the current working directory.
    history_limit:
        Maximum number of prior conversation turns to include as context
        when calling the LLM. Defaults to 20 (10 exchanges).
    """

    def __init__(
        self,
        optimizer: ProfitabilityOptimizer | None = None,
        backend: LLMBackend | None = None,
        persona: Persona | None = None,
        data_dir: str | os.PathLike[str] = "data",
        history_limit: int = 20,
    ) -> None:
        self.optimizer = optimizer or ProfitabilityOptimizer()
        self.backend = backend or default_backend()
        self.persona = persona or default_persona()
        self.data_dir = Path(data_dir)
        self.history_limit = history_limit
        self.profiles = ProfileStore(self.data_dir)
        self.audit = AuditLog(self.data_dir)

    def _memory(self, user_id: str) -> ConversationMemory:
        return ConversationMemory(user_id, self.data_dir)

    def _load_profile(self, user_id: str) -> UserProfile:
        profile = self.profiles.load(user_id)
        if profile is None:
            profile = UserProfile(user_id=user_id)
            self.profiles.save(profile)
        return profile

    def _format_history(self, messages: list[Message]) -> str:
        if not messages:
            return "(no prior messages)"
        lines = [f"{m.role}: {m.content}" for m in messages]
        return "\n".join(lines)

    def ask(
        self,
        user_id: str,
        question: str,
        rig: Rig,
        coins: Iterable[Coin],
        electricity_cost_per_kwh: float,
    ) -> AssistantReply:
        """Answer ``question`` for ``user_id`` using optimizer + memory.

        The user's message, the assistant's answer, and a structured
        recommendation record are written to disk before the method
        returns. The returned :class:`AssistantReply` carries the
        answer, whether it was refused, and the exact numbers the
        answer was based on.
        """
        memory = self._memory(user_id)
        memory.append("user", question)

        profile = self._load_profile(user_id)

        coin_list = list(coins)
        rankings = self.optimizer.rank(
            rig, coin_list, electricity_cost_per_kwh
        )
        payload = _rankings_to_payload(rig, electricity_cost_per_kwh, rankings)
        payload["profile"] = profile.to_dict()

        if should_refuse(self.persona, question):
            answer = refusal_response(self.persona)
            memory.append("assistant", answer)
            self.audit.append(
                kind="refusal",
                user_id=user_id,
                payload={"question": question, "reason": "refusal_topic"},
            )
            return AssistantReply(answer=answer, refused=True, payload=payload)

        history = memory.load(limit=self.history_limit)
        user_message = (
            f"User profile: {profile.summary()}\n\n"
            f"Prior conversation:\n{self._format_history(history[:-1])}\n\n"
            f"New question: {question}\n\n"
            f"Context (JSON):\n{json.dumps(payload, indent=2)}"
        )
        logger.debug("Dispatching to %s", type(self.backend).__name__)
        answer = self.backend.complete(self.persona.system_prompt, user_message)

        memory.append("assistant", answer)
        self.audit.append(
            kind="recommendation",
            user_id=user_id,
            payload={
                "question": question,
                "rankings": payload["rankings"],
                "electricity_cost_per_kwh": electricity_cost_per_kwh,
                "answer": answer,
            },
        )
        return AssistantReply(answer=answer, refused=False, payload=payload)


__all__ = [
    "AnthropicBackend",
    "AssistantReply",
    "LLMBackend",
    "MiningAssistant",
    "MockBackend",
    "OpenAIBackend",
    "SYSTEM_PROMPT",
    "default_backend",
]
