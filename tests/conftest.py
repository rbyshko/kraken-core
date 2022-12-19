from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

from pytest import fixture


@fixture
def tempdir() -> Iterator[Path]:
    with TemporaryDirectory() as tempdir:
        yield Path(tempdir)
