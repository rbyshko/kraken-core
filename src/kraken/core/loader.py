""" Implements a loader for Python scripts. These Python scripts have access to importing certain build context
related members from the :mod:`kraken.api` module; note that these members are only available when imported in
the context of a script executed by this loader and not otherwise. """

from __future__ import annotations

import abc
import types
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kraken.core.project import Project


class ProjectLoaderError(Exception):
    def __init__(self, project: Project, message: str) -> None:
        self.project = project
        self.message = message

    def __str__(self) -> str:
        return f"[{self.project.path}] {self.message}"


class ProjectHasNoBuildScriptError(ProjectLoaderError):
    pass


class ProjectLoader(abc.ABC):
    @abc.abstractmethod
    def load_project(self, project: Project) -> None:
        """
        :param project: The project to load the build script into.
        """


class PythonScriptProjectLoader(ProjectLoader):
    BUILD_SCRIPT = Path(".kraken.py")

    def load_project(self, project: Project) -> None:
        file = project.directory / self.BUILD_SCRIPT
        if not file.is_file():
            raise ProjectHasNoBuildScriptError(project, f"file {file!r} does not exist")

        with project.as_current():
            code = compile(file.read_text(), filename=file, mode="exec")
            module = types.ModuleType(project.path)
            module.__file__ = str(file)
            exec(code, vars(module))
