from __future__ import annotations

from pathlib import Path

import pytest

from software.profile import ProfileStore, UserProfile
from software.profitability import Rig


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    store = ProfileStore(root=tmp_path)
    profile = UserProfile(
        user_id="alice",
        display_name="Alice",
        stated_goal="extra income for vacations",
        risk_tolerance="low",
        electricity_cost_per_kwh=0.11,
        rig=Rig(hashrate_hs=50e12, power_watts=1500),
        notes=["prefers SHA-256 coins"],
    )
    store.save(profile)
    loaded = store.load("alice")
    assert loaded is not None
    assert loaded.display_name == "Alice"
    assert loaded.rig is not None
    assert loaded.rig.hashrate_hs == 50e12
    assert loaded.notes == ["prefers SHA-256 coins"]


def test_load_missing_returns_none(tmp_path: Path) -> None:
    assert ProfileStore(root=tmp_path).load("nobody") is None


def test_summary_includes_key_fields() -> None:
    profile = UserProfile(
        user_id="alice",
        display_name="Alice",
        stated_goal="vacations",
        electricity_cost_per_kwh=0.12,
    )
    summary = profile.summary()
    assert "alice" in summary
    assert "Alice" in summary
    assert "vacations" in summary
    assert "0.120" in summary


@pytest.mark.parametrize("bad_id", ["", "../escape", "a/b"])
def test_invalid_user_id_rejected(tmp_path: Path, bad_id: str) -> None:
    store = ProfileStore(root=tmp_path)
    with pytest.raises(ValueError):
        store.load(bad_id)
