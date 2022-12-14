from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

from pytest import fixture

from kraken.core.test import kraken_project  # noqa: F401


@fixture
def tempdir() -> Iterator[Path]:
    with TemporaryDirectory() as tempdir:
        yield Path(tempdir)
