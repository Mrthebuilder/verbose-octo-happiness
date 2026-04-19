"""File integrity self-check.

We take a SHA-256 hash of every ``*.py`` file under the package, compare
it against a manifest, and report any mismatches. The manifest can be
generated once per release and committed; at runtime the assistant
checks itself against the pinned manifest on every startup (and on
demand) and refuses to operate if files have been modified.

This is not a substitute for signed releases, but it means a process
running against a tampered-with install has to also tamper with the
manifest *and* the public-key that verifies it — which is exactly the
layered defense you want.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class IntegrityReport:
    """Result of comparing on-disk files against a manifest."""

    ok: bool
    missing: tuple[str, ...] = field(default_factory=tuple)
    unexpected: tuple[str, ...] = field(default_factory=tuple)
    mismatched: tuple[str, ...] = field(default_factory=tuple)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_manifest(
    root: str | os.PathLike[str], pattern: str = "*.py"
) -> dict[str, str]:
    """Return a ``{relative_path: sha256}`` mapping under ``root``."""
    root_path = Path(root)
    manifest: dict[str, str] = {}
    for path in sorted(root_path.rglob(pattern)):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root_path))
        manifest[rel] = _sha256_file(path)
    return manifest


def verify_manifest(
    root: str | os.PathLike[str], manifest: dict[str, str]
) -> IntegrityReport:
    """Compare on-disk files to ``manifest`` and return a report."""
    current = compute_manifest(root)
    missing = tuple(sorted(k for k in manifest if k not in current))
    unexpected = tuple(sorted(k for k in current if k not in manifest))
    mismatched = tuple(
        sorted(k for k in manifest if k in current and current[k] != manifest[k])
    )
    ok = not (missing or unexpected or mismatched)
    return IntegrityReport(
        ok=ok,
        missing=missing,
        unexpected=unexpected,
        mismatched=mismatched,
    )


def write_manifest(path: str | os.PathLike[str], manifest: dict[str, str]) -> None:
    """Write a manifest to disk as pretty-printed JSON."""
    with Path(path).open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)


def read_manifest(path: str | os.PathLike[str]) -> dict[str, str]:
    """Read a manifest written by :func:`write_manifest`."""
    with Path(path).open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in data.items()
    ):
        raise ValueError("manifest must be a JSON object of str -> str")
    return data


__all__ = [
    "IntegrityReport",
    "compute_manifest",
    "read_manifest",
    "verify_manifest",
    "write_manifest",
]
