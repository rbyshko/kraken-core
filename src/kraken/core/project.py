from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Optional, Type, TypeVar, cast, overload

import builddsl
from deprecated import deprecated

from kraken.core.base import Currentable, MetadataContainer
from kraken.core.task import GroupTask, Task, TaskSet

if TYPE_CHECKING:
    from kraken.core.context import Context

T = TypeVar("T")
T_Task = TypeVar("T_Task", bound="Task")


class ProjectLoaderError(Exception):
    def __init__(self, project: Project, message: str) -> None:
        self.project = project
        self.message = message

    def __str__(self) -> str:
        return f"[{self.project.path}] {self.message}"


class Project(MetadataContainer, Currentable["Project"]):
    """A project consolidates tasks related to a directory on the filesystem."""

    name: str
    directory: Path
    parent: Optional[Project]
    context: Context
    metadata: list[Any]  #: A list of arbitrary objects that are usually looked up by type.

    def __init__(self, name: str, directory: Path, parent: Optional[Project], context: Context) -> None:
        self.name = name
        self.directory = directory
        self.parent = parent
        self.context = context
        self.metadata = []

        # We store all members that can be referenced by a fully qualified name in the same dictionary to ensure
        # we're not accidentally allocating the same name twice.
        self._members: dict[str, Task | Project] = {}

        apply_group = self.group(
            "apply", description="Tasks that perform automatic updates to the project consistency."
        )
        fmt_group = self.group("fmt", description="Tasks that that perform code formatting operations.")
        fmt_group.add_relationship(apply_group, strict=True)

        check_group = self.group("check", description="Tasks that perform project consistency checks.", default=True)

        lint_group = self.group("lint", description="Tasks that perform code linting.", default=True)
        lint_group.add_relationship(check_group, strict=True)

        build_group = self.group("build", description="Tasks that produce build artefacts.")
        build_group.add_relationship(lint_group, strict=False)

        test_group = self.group("test", description="Tasks that perform unit tests.", default=True)
        test_group.add_relationship(build_group, strict=False)

        integration_test_group = self.group("integrationTest", description="Tasks that perform integration tests.")
        integration_test_group.add_relationship(test_group, strict=False)

        publish_group = self.group("publish", description="Tasks that publish build artefacts.")
        publish_group.add_relationship(integration_test_group, strict=False)

        deploy_group = self.group("deploy", description="Tasks that deploy applications.")
        deploy_group.add_relationship(publish_group, strict=False)

    def __repr__(self) -> str:
        return f"Project({self.path})"

    @property
    def path(self) -> str:
        """Returns the path that uniquely identifies the project in the current build context."""

        if self.parent is None:
            return ":"
        elif self.parent.parent is None:
            return f":{self.name}"
        else:
            return f"{self.parent.path}:{self.name}"

    @property
    def build_directory(self) -> Path:
        """Returns the recommended build directory for the project; this is a directory inside the context
        build directory ammended by the project name."""

        return self.context.build_directory / self.path.replace(":", "/").lstrip("/")

    def task(self, name: str) -> Task:
        """Return a task in the project by name."""

        task = self._members[name]
        if not isinstance(task, Task):
            raise ValueError(f"name {name!r} does not refer to a task, but {type(task).__name__}")
        return task

    def tasks(self) -> Mapping[str, Task]:
        return {t.name: t for t in self._members.values() if isinstance(t, Task)}

    @deprecated(reason="use Project.subprojects() or Project.subproject() instead")
    def children(self) -> Mapping[str, Project]:
        return self.subprojects()

    def subprojects(self) -> Mapping[str, Project]:
        return {p.name: p for p in self._members.values() if isinstance(p, Project)}

    @overload
    def subproject(self, name: str) -> Project:
        ...

    @overload
    def subproject(self, name: str, load: bool) -> Project | None:
        ...

    def subproject(self, name: str, load: bool = True) -> Project | None:
        """
        Returns the subproject of this project that has the specified *name*. If no such subproject exists yet,
        it will be created and loaded, however a folder of that *name* must exist. If the folder contains a Kraken
        build script, that script will also be loaded.
        """

        obj = self._members.get(name)
        if obj is not None:
            if not isinstance(obj, Project):
                raise ValueError(f"{self.path}:{name} does not refer to a project (got {type(obj).__name__} instead)")
            return obj

        if not load:
            return None

        directory = self.directory / name
        if not directory.is_dir():
            raise FileNotFoundError(
                f"{self.path}:{name} cannot be loaded because the directory {directory} does not exist"
            )

        project = self.context.load_project(directory, self, require_buildscript=False)
        assert name in self._members
        assert self._members[name] is project

        return project

    def has_subproject(self, name: str) -> bool:
        """
        Returns `True` if *name* refers to a subproject that exists in the current project.
        """

        return isinstance(self._members.get(name), Project)

    def resolve_tasks(self, tasks: str | Task | Iterable[str | Task]) -> TaskSet:
        """Resolve tasks relative to the current project."""

        if isinstance(tasks, (str, Task)):
            tasks = [tasks]

        result = TaskSet()
        for item in tasks:
            if isinstance(item, str):
                result.add(self.context.resolve_tasks([item], self), partition=item)
            else:
                result.add([item])

        return result

    def add_task(self, task: Task) -> None:
        """Adds a task to the project.

        Raises:
            ValueError: If a member with the same name already exists or if the task's project does not match
        """

        if task.name in self._members:
            raise ValueError(f"{self} already has a member {task.name!r}, cannot add {task}")
        if task.project is not self:
            raise ValueError(f"{task}.project mismatch")
        self._members[task.name] = task

    def add_child(self, project: Project) -> None:
        """Adds a project as a child project.

        Raises:
            ValueError: If a member with the same name already exists or if the project's parent does not match
        """

        if project.name in self._members:
            raise ValueError(f"{self} already has a member {project.name!r}, cannot add {project}")
        if project.parent is not self:
            raise ValueError(f"{project}.parent mismatch")
        self._members[project.name] = project

    def remove_child(self, project: Project) -> None:
        assert project.parent is self
        assert self._members[project.name] is project

        del self._members[project.name]

    def do(
        self,
        name: str,
        task_type: Type[T_Task] = cast(Any, Task),
        default: bool | builddsl.UnboundClosure | None = None,
        *,
        group: str | GroupTask | None = None,
        description: str | None = None,
        **kwargs: Any,
    ) -> T_Task:
        """Add a task to the project under the given name, executing the specified action.

        :param name: The name of the task to add.
        :param task_type: The type of task to add.
        :param default: Override :attr:`Task.default`, or a closure to invoke with the created task.
        :param group: Add the task to the given group in the project.
        :param kwargs: Any number of properties to set on the task. Unknown properties will be ignored
            with a warning log.
        :return: The created task.
        """

        if name in self._members:
            raise ValueError(f"{self} already has a member {name!r}")

        task = task_type(name, self)
        if default is not None and not isinstance(default, builddsl.UnboundClosure):
            task.default = default
        if description is not None:
            task.description = description
        task.update(**kwargs)
        if isinstance(default, builddsl.UnboundClosure):
            default(task)
        self.add_task(task)
        if isinstance(group, str):
            group = self.group(group)
        if group is not None:
            group.add(task)
        return task

    def group(self, name: str, *, description: str | None = None, default: bool | None = None) -> GroupTask:
        """Create or get a group of the given name. If a task with the given name already exists, it must refer
        to a task of type :class:`GroupTask`, otherwise a :class:`RuntimeError` is raised.

        :param name: The name of the group in the project.
        :param description: If specified, set the group's description.
        :param default: Whether the task group is run by default."""

        task = self.tasks().get(name)
        if task is None:
            task = self.do(name, GroupTask)
        elif not isinstance(task, GroupTask):
            raise RuntimeError(f"{task.path!r} must be a GroupTask, but got {type(task).__name__}")
        if description is not None:
            task.description = description
        if default is not None:
            task.default = default

        return task
