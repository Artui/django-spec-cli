from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from django.core.management.base import CommandError
from django_service_specs import FileResult

from django_spec_cli.types.exit_code import ExitCode


def write_file(presented: FileResult | None, sink: Path | BinaryIO) -> str | None:
    """Write a file spec's presented result to ``sink``, and answer the line naming it.

    ``presented`` is what
    [`present`][django_service_specs.dispatch.present.present] returned for a
    spec that presents through a
    [`FilePresenter`][django_service_specs.output.file_presenter.FilePresenter]:
    a [`FileResult`][django_service_specs.types.file_result.FileResult], or
    ``None`` from an ``allow_none`` spec that found nothing, for which nothing
    is written, no file is created and ``None`` is answered.

    The content is read whole, and closed, before ``sink`` is touched, so a
    file the read fails on leaves a file already at a ``Path`` as it was.
    ``sink`` is a ``Path``, written as its bytes and replacing what is there,
    or a binary stream such as stdout's ``buffer``, written and flushed. The
    result's ``filename`` is never joined to ``sink``: a ``Path`` naming a
    directory is refused with ``CommandError``, ``ExitCode.ERROR``, as is any
    other path the operating system will not write.

    The answer, ``"<filename> (<content type>, <n> bytes)"``, is for stderr,
    so a person sees the name the operation gave the file without it reaching
    the bytes on stdout.
    """
    if presented is None:
        return None
    data = presented.read()
    if isinstance(sink, Path):
        try:
            sink.write_bytes(data)
        except OSError as error:
            raise CommandError(
                f"Could not write the file to {str(sink)!r}: {error.strerror or error}.",
                returncode=int(ExitCode.ERROR),
            ) from error
    else:
        sink.write(data)
        sink.flush()
    return f"{presented.filename} ({presented.content_type}, {len(data)} bytes)"
