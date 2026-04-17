from __future__ import annotations

from pathlib import Path

from software.integrity import (
    compute_manifest,
    read_manifest,
    verify_manifest,
    write_manifest,
)


def _populate(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print('a')\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_text("print('b')\n", encoding="utf-8")


def test_matching_manifest_reports_ok(tmp_path: Path) -> None:
    _populate(tmp_path)
    manifest = compute_manifest(tmp_path)
    report = verify_manifest(tmp_path, manifest)
    assert report.ok
    assert not report.missing
    assert not report.unexpected
    assert not report.mismatched


def test_modified_file_is_mismatched(tmp_path: Path) -> None:
    _populate(tmp_path)
    manifest = compute_manifest(tmp_path)
    (tmp_path / "a.py").write_text("print('tampered')\n", encoding="utf-8")
    report = verify_manifest(tmp_path, manifest)
    assert not report.ok
    assert "a.py" in report.mismatched


def test_new_file_is_unexpected(tmp_path: Path) -> None:
    _populate(tmp_path)
    manifest = compute_manifest(tmp_path)
    (tmp_path / "injected.py").write_text("print('evil')\n", encoding="utf-8")
    report = verify_manifest(tmp_path, manifest)
    assert not report.ok
    assert "injected.py" in report.unexpected


def test_deleted_file_is_missing(tmp_path: Path) -> None:
    _populate(tmp_path)
    manifest = compute_manifest(tmp_path)
    (tmp_path / "a.py").unlink()
    report = verify_manifest(tmp_path, manifest)
    assert not report.ok
    assert "a.py" in report.missing


def test_write_and_read_manifest_roundtrip(tmp_path: Path) -> None:
    _populate(tmp_path)
    manifest = compute_manifest(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, manifest)
    assert read_manifest(manifest_path) == manifest
