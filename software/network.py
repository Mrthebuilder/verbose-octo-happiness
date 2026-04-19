"""Network-posture self-check for the Brick appliance.

The Brick is designed to be an outbound-only device: it reaches out to
a small, pinned set of hosts (price feeds, pool APIs, update server)
and nothing else. Nothing initiates a connection *to* the Brick. No
Bluetooth, no discovery protocols, no remote-shell daemon.

This module performs *startup self-checks*. It is a belt-and-suspenders
layer that complements (not replaces) a properly configured host
firewall. On a production Brick, the firewall is the real enforcement
(see ``docs/HARDWARE_SPEC.md``); this module catches misconfigurations
before Brick accepts user questions.

The checks are best-effort and Linux-oriented because that is the
Brick's reference operating environment. On other platforms most
checks gracefully skip instead of lying. Nothing here reaches the
network; every check is local.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BANNED_PROCESSES: frozenset[str] = frozenset(
    {
        "sshd",
        "bluetoothd",
        "bluetooth",
        "avahi-daemon",
        "vncserver",
        "x11vnc",
        "anydesk",
        "teamviewer",
        "telnetd",
    }
)


@dataclass(frozen=True)
class NetworkReport:
    """Result of a network-posture self-check."""

    ok: bool
    offending_processes: tuple[str, ...] = field(default_factory=tuple)
    listening_sockets: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    skipped: tuple[str, ...] = field(default_factory=tuple)


def _read_proc_comm_names(proc_root: Path) -> set[str]:
    """Return the set of ``comm`` names under ``/proc``.

    ``/proc/<pid>/comm`` is the short process name the kernel keeps
    for each task. This is a lightweight way to enumerate running
    processes without pulling in ``psutil``.
    """
    names: set[str] = set()
    if not proc_root.exists():
        return names
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        comm = entry / "comm"
        try:
            name = comm.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if name:
            names.add(name)
    return names


def scan_banned_processes(
    banned: Iterable[str] = DEFAULT_BANNED_PROCESSES,
    proc_root: Path | str = Path("/proc"),
) -> tuple[tuple[str, ...], bool]:
    """Return ``(found, ran)``.

    ``found`` is the sorted tuple of banned process names that are
    currently running. ``ran`` is ``False`` if we could not enumerate
    processes on this host (e.g. non-Linux, no ``/proc``).
    """
    proc_path = Path(proc_root)
    if not proc_path.exists():
        return (), False
    if str(proc_path) == "/proc" and not sys.platform.startswith("linux"):
        return (), False
    running = _read_proc_comm_names(proc_path)
    banned_set = {name.lower() for name in banned}
    hits = sorted(n for n in running if n.lower() in banned_set)
    return tuple(hits), True


def _run_ss(cmd: list[str]) -> tuple[str, bool]:
    """Run ``ss`` (or ``netstat``) and return ``(stdout, ran)``."""
    exe = cmd[0]
    if shutil.which(exe) is None:
        return "", False
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "", False
    if proc.returncode != 0:
        return proc.stdout or "", False
    return proc.stdout or "", True


def _parse_ss_output(output: str) -> list[tuple[str, int]]:
    """Parse ``ss -H -tulnp`` output into ``(proto, port)`` tuples."""
    rows: list[tuple[str, int]] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        proto = parts[0]
        local = parts[4]
        if ":" not in local:
            continue
        try:
            port = int(local.rsplit(":", 1)[1])
        except ValueError:
            continue
        rows.append((proto, port))
    return rows


def scan_listening_sockets(
    allowed_ports: Iterable[int] = (),
) -> tuple[tuple[str, ...], bool]:
    """Return ``(offending_lines, ran)``.

    Offending sockets are listening sockets on ports that are not in
    ``allowed_ports``. ``ran`` is ``False`` if we could not introspect
    listening sockets on this host.
    """
    out, ran = _run_ss(["ss", "-H", "-tulnp"])
    if not ran:
        return (), False
    allowed = set(allowed_ports)
    rows = _parse_ss_output(out)
    offenders = tuple(
        f"{proto} port {port}" for proto, port in rows if port not in allowed
    )
    return offenders, True


def verify_network_posture(
    banned: Iterable[str] = DEFAULT_BANNED_PROCESSES,
    allowed_ports: Iterable[int] = (),
    proc_root: Path | str = Path("/proc"),
) -> NetworkReport:
    """Run every check and return a consolidated :class:`NetworkReport`."""
    warnings: list[str] = []
    skipped: list[str] = []

    offenders, procs_ran = scan_banned_processes(banned, proc_root=proc_root)
    if not procs_ran:
        skipped.append("scan_banned_processes (requires Linux /proc)")

    listening, listen_ran = scan_listening_sockets(allowed_ports=allowed_ports)
    if not listen_ran:
        skipped.append("scan_listening_sockets (requires `ss` command)")

    if procs_ran and offenders:
        warnings.append(
            "Banned services detected; Brick should refuse to start."
        )
    if listen_ran and listening:
        warnings.append(
            "Listening sockets detected; the Brick reference design is "
            "outbound-only."
        )

    ok = (not procs_ran or not offenders) and (
        not listen_ran or not listening
    )

    return NetworkReport(
        ok=ok,
        offending_processes=offenders,
        listening_sockets=listening,
        warnings=tuple(warnings),
        skipped=tuple(skipped),
    )


__all__ = [
    "DEFAULT_BANNED_PROCESSES",
    "NetworkReport",
    "scan_banned_processes",
    "scan_listening_sockets",
    "verify_network_posture",
]
