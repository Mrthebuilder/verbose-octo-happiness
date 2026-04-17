from __future__ import annotations

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


def test_refusal_response_mentions_advisor_and_persona_name() -> None:
    persona = default_persona()
    response = refusal_response(persona)
    assert persona.name in response
    assert "advisor" in response.lower()
