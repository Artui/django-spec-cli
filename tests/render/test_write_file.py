from __future__ import annotations

import io
from pathlib import Path

import pytest
from django.core.management.base import CommandError
from django_service_specs import FileResult

from django_spec_cli.render.write_file import write_file


def _file(content: bytes | io.BytesIO = b"a,b\n") -> FileResult:
    return FileResult(content, filename="rows.csv", content_type="text/csv")


def test_a_stream_receives_the_bytes_and_the_answer_names_the_file() -> None:
    stream = io.BytesIO()
    assert write_file(_file(), stream) == "rows.csv (text/csv, 4 bytes)"
    assert stream.getvalue() == b"a,b\n"


def test_a_path_receives_the_bytes_and_the_content_is_closed(tmp_path: Path) -> None:
    content = io.BytesIO(b"x" * 70_000)
    target = tmp_path / "out.csv"
    assert write_file(_file(content), target) == "rows.csv (text/csv, 70000 bytes)"
    assert (target.read_bytes(), content.closed) == (b"x" * 70_000, True)


def test_nothing_presented_writes_nothing_and_answers_none(tmp_path: Path) -> None:
    target = tmp_path / "out.csv"
    assert write_file(None, target) is None
    assert not target.exists()


def test_a_path_the_system_will_not_write_is_a_command_error(tmp_path: Path) -> None:
    target = tmp_path / "missing" / "out.csv"
    with pytest.raises(CommandError, match="No such file or directory") as caught:
        write_file(_file(), target)
    assert caught.value.returncode == 1


def test_a_failed_read_leaves_the_path_as_it_was(tmp_path: Path) -> None:
    target = tmp_path / "out.csv"
    target.write_bytes(b"old")
    with pytest.raises(TypeError):
        write_file(FileResult(["text"], filename="rows.csv"), target)
    assert target.read_bytes() == b"old"
