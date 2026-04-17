"""Per-user profile persisted as JSON on disk.

The profile is everything the assistant needs to personalize its
answers: who the user is, what they're saving for, what their rig can
do, and what they've told us about their risk tolerance.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .profitability import Rig


@dataclass
class UserProfile:
    """Everything we know about a single user."""

    user_id: str
    display_name: str = ""
    stated_goal: str = ""  # e.g. "extra income", "save for a new rig"
    risk_tolerance: str = "unspecified"  # "low", "medium", "high", "unspecified"
    electricity_cost_per_kwh: float = 0.0
    rig: Rig | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.rig is not None:
            data["rig"] = asdict(self.rig)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> UserProfile:
        rig_data = data.get("rig")
        rig = Rig(**rig_data) if isinstance(rig_data, dict) else None
        return cls(
            user_id=str(data["user_id"]),
            display_name=str(data.get("display_name", "")),
            stated_goal=str(data.get("stated_goal", "")),
            risk_tolerance=str(data.get("risk_tolerance", "unspecified")),
            electricity_cost_per_kwh=float(
                data.get("electricity_cost_per_kwh", 0.0)
            ),
            rig=rig,
            notes=list(data.get("notes", [])),
        )

    def summary(self) -> str:
        """One-paragraph summary suitable for injecting into a prompt."""
        parts = [f"user_id={self.user_id}"]
        if self.display_name:
            parts.append(f"name={self.display_name}")
        if self.stated_goal:
            parts.append(f"goal={self.stated_goal}")
        parts.append(f"risk_tolerance={self.risk_tolerance}")
        if self.electricity_cost_per_kwh:
            parts.append(
                f"electricity=${self.electricity_cost_per_kwh:.3f}/kWh"
            )
        if self.rig is not None:
            parts.append(
                f"rig={self.rig.hashrate_hs:.2e}H/s @ {self.rig.power_watts}W"
            )
        return "; ".join(parts)


class ProfileStore:
    """Read/write :class:`UserProfile` records as JSON on disk."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)

    def _path(self, user_id: str) -> Path:
        if not user_id or "/" in user_id or ".." in user_id:
            raise ValueError("user_id must be a simple identifier")
        return self.root / user_id / "profile.json"

    def load(self, user_id: str) -> UserProfile | None:
        path = self._path(user_id)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as fh:
            return UserProfile.from_dict(json.load(fh))

    def save(self, profile: UserProfile) -> None:
        path = self._path(profile.user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a tempfile then atomic rename so concurrent readers never
        # see a half-written file.
        tmp = path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(profile.to_dict(), fh, indent=2, ensure_ascii=False)
        tmp.replace(path)


__all__ = ["ProfileStore", "UserProfile"]
