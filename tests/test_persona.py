from __future__ import annotations

import pytest

from software.persona import (
    FINANCIAL_DISCLAIMER,
    default_persona,
    refusal_response,
    should_refuse,
)


def test_default_persona_has_name_and_system_prompt() -> None:
    persona = default_persona()
    assert persona.name == "Brick"
    assert persona.system_prompt
    assert FINANCIAL_DISCLAIMER in persona.system_prompt


def test_refusal_fires_on_retirement_question() -> None:
    persona = default_persona()
    assert should_refuse(persona, "Should I put my retirement into mining?")
    assert should_refuse(persona, "mortgage the house to buy rigs?")
    assert should_refuse(persona, "use my kids' college fund to mine?")


def test_refusal_ignores_benign_questions() -> None:
    persona = default_persona()
    assert not should_refuse(persona, "Which coin is most profitable right now?")
    assert not should_refuse(persona, "What's my break-even price for BTC?")


@pytest.mark.parametrize(
    "question",
    [
        "What are my mining aspirations?",
        "I like pirate-themed rig names",
        "Would a viral marketing campaign help?",
        "Miranda asked about hashrate",
        "These numbers look admirable",
        "It would be desirable to lower power draw",
        "That's a miracle hashrate",
    ],
)
def test_refusal_does_not_false_positive_on_substrings(question: str) -> None:
    # "ira" used to bare-substring-match inside words like "pirate",
    # "aspiration", and "admirable", causing benign questions to get
    # hard-refused. Word-boundary matching fixes that.
    #
    # Note: we deliberately still match the literal word "retirement"
    # even if the user meant a coin's retirement, not their own. That's
    # a fail-closed choice — if a user says the word "retirement" we'd
    # rather refuse and ask for clarification than risk giving real
    # retirement advice through a loophole.
    persona = default_persona()
    assert not should_refuse(persona, question)


@pytest.mark.parametrize(
    "question",
    [
        "Should I roll my IRA into this?",
        "moving my roth ira to mining",
        "Can I mine with my 401(k)?",
        "Should I put my 401k into this?",
    ],
)
def test_refusal_still_catches_short_topics_as_words(question: str) -> None:
    persona = default_persona()
    assert should_refuse(persona, question)


def test_refusal_response_mentions_advisor_and_persona_name() -> None:
    persona = default_persona()
    response = refusal_response(persona)
    assert persona.name in response
    assert "advisor" in response.lower()
