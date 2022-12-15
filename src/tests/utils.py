import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def chdir_context(path: Path) -> Iterator[None]:
    cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(cwd)
