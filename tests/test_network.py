from __future__ import annotations

from pathlib import Path

import pytest

from software import network as net
from software.network import (
    DEFAULT_BANNED_PROCESSES,
    _parse_ss_output,
    scan_banned_processes,
    verify_network_posture,
)


def _fake_proc(root: Path, pids_and_comm: list[tuple[int, str]]) -> Path:
    """Build a fake /proc-like tree for testing scan_banned_processes."""
    for pid, comm in pids_and_comm:
        pid_dir = root / str(pid)
        pid_dir.mkdir(parents=True, exist_ok=True)
        (pid_dir / "comm").write_text(comm + "\n", encoding="utf-8")
    return root


def test_scan_banned_processes_flags_banned(tmp_path: Path) -> None:
    proc = _fake_proc(
        tmp_path,
        [(1, "systemd"), (42, "sshd"), (100, "bluetoothd"), (200, "brickd")],
    )
    found, ran = scan_banned_processes(
        banned=DEFAULT_BANNED_PROCESSES, proc_root=proc
    )
    assert ran is True
    assert "sshd" in found
    assert "bluetoothd" in found
    assert "brickd" not in found


def test_scan_banned_processes_clean_host(tmp_path: Path) -> None:
    proc = _fake_proc(tmp_path, [(1, "systemd"), (200, "brickd")])
    found, ran = scan_banned_processes(
        banned=DEFAULT_BANNED_PROCESSES, proc_root=proc
    )
    assert ran is True
    assert found == ()


def test_scan_banned_processes_missing_proc_dir(tmp_path: Path) -> None:
    found, ran = scan_banned_processes(
        banned=DEFAULT_BANNED_PROCESSES, proc_root=tmp_path / "does-not-exist"
    )
    assert ran is False
    assert found == ()


def test_parse_ss_output_extracts_ports() -> None:
    sample = (
        "tcp   LISTEN 0 128 0.0.0.0:22   0.0.0.0:* users:((\"sshd\"))\n"
        "udp   UNCONN 0 0   0.0.0.0:5353 0.0.0.0:* users:((\"avahi\"))\n"
        "tcp   LISTEN 0 128 [::]:443     [::]:*    users:((\"nginx\"))\n"
        "\n"
    )
    rows = _parse_ss_output(sample)
    assert ("tcp", 22) in rows
    assert ("udp", 5353) in rows
    assert ("tcp", 443) in rows


def test_verify_network_posture_on_clean_fake_proc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A clean fake /proc with only innocuous processes and a stubbed
    # listening-socket scan so the result is deterministic regardless
    # of whatever real ports happen to be open on the host.
    _fake_proc(tmp_path, [(1, "systemd"), (200, "brickd")])
    monkeypatch.setattr(net, "scan_listening_sockets", lambda **_: ((), True))
    report = verify_network_posture(
        banned=DEFAULT_BANNED_PROCESSES, proc_root=tmp_path
    )
    assert report.offending_processes == ()
    assert report.listening_sockets == ()
    assert report.ok is True


def test_verify_network_posture_flags_banned_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_proc(tmp_path, [(1, "systemd"), (42, "sshd")])
    monkeypatch.setattr(net, "scan_listening_sockets", lambda **_: ((), True))
    report = verify_network_posture(
        banned=DEFAULT_BANNED_PROCESSES, proc_root=tmp_path
    )
    assert "sshd" in report.offending_processes
    assert report.ok is False
    assert any("Banned services" in w for w in report.warnings)


def test_verify_network_posture_flags_listening_sockets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_proc(tmp_path, [(1, "systemd")])
    monkeypatch.setattr(
        net,
        "scan_listening_sockets",
        lambda **_: (("tcp port 22",), True),
    )
    report = verify_network_posture(
        banned=DEFAULT_BANNED_PROCESSES, proc_root=tmp_path
    )
    assert report.ok is False
    assert "tcp port 22" in report.listening_sockets
    assert any("Listening sockets" in w for w in report.warnings)
