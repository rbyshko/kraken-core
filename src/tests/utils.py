import os
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def chdir_context(path: Path) -> None:
    cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(cwd)
