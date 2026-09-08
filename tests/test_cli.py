from pathlib import Path

import pytest

from agentic_api import cli


def test_safe_write_atomically_replaces_existing_file(tmp_path, monkeypatch):
    destination = tmp_path / "nested" / "artifact.txt"
    destination.parent.mkdir()
    destination.write_text("old content", encoding="utf-8")

    def reject_in_place_write(*args, **kwargs):
        raise AssertionError("Path.write_text would overwrite the cloud placeholder in place")

    monkeypatch.setattr(Path, "write_text", reject_in_place_write)

    cli._safe_write(tmp_path, "nested/artifact.txt", "new content")

    assert destination.read_text(encoding="utf-8") == "new content"
    assert not list(destination.parent.glob(".artifact.txt.*.tmp"))


def test_safe_write_preserves_old_file_if_replace_fails(tmp_path, monkeypatch):
    destination = tmp_path / "artifact.txt"
    destination.write_text("old content", encoding="utf-8")

    def fail_replace(*args, **kwargs):
        raise OSError("simulated replacement failure")

    monkeypatch.setattr(cli.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replacement failure"):
        cli._safe_write(tmp_path, "artifact.txt", "new content")

    assert destination.read_text(encoding="utf-8") == "old content"
    assert not list(tmp_path.glob(".artifact.txt.*.tmp"))


def test_write_progress_identifies_file_size_and_position(tmp_path, capsys):
    cli._write_with_progress(
        root=tmp_path,
        relative_path="artifact.txt",
        content="x" * 1024,
        current=2,
        total=4,
    )

    assert capsys.readouterr().err == "[2/4] Writing artifact.txt (1.0 KiB)\n"
    assert (tmp_path / "artifact.txt").read_text(encoding="utf-8") == "x" * 1024
