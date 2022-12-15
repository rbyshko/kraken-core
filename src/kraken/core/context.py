from __future__ import annotations

import collections
import dataclasses
import enum
import logging
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Iterable,
    Iterator,
    MutableMapping,
    Optional,
    Sequence,
    TypeVar,
    overload,
)

from kraken.common import CurrentDirectoryProjectFinder, ProjectFinder, ScriptRunner
from typing_extensions import TypeAlias

from kraken.core.base import Currentable, MetadataContainer
from kraken.core.executor import GraphExecutorObserver

if TYPE_CHECKING:
    from kraken.core.executor import GraphExecutor
    from kraken.core.graph import TaskGraph
    from kraken.core.project import Project
    from kraken.core.task import Task

logger = logging.getLogger(__name__)
T = TypeVar("T")


class ContextEventType(enum.Enum):
    any = enum.auto()
    on_project_init = enum.auto()  # event data type is Project
    on_project_loaded = enum.auto()  # event data type is Project
    on_project_begin_finalize = enum.auto()  # event data type is Project
    on_project_finalized = enum.auto()  # event data type is Project
    on_context_begin_finalize = enum.auto()  # event data type is Context
    on_context_finalized = enum.auto()  # event data type is Context


@dataclasses.dataclass
class ContextEvent:

    Type: ClassVar[TypeAlias] = ContextEventType
    Listener = Callable[["ContextEvent"], Any]
    T_Listener = TypeVar("T_Listener", bound=Listener)

    type: Type
    data: Any  # Depends on the event type


class Context(MetadataContainer, Currentable["Context"]):
    """This class is the single instance where all components of a build process come together."""

    def __init__(
        self,
        build_directory: Path,
        project_finder: ProjectFinder | None = None,
        executor: GraphExecutor | None = None,
        observer: GraphExecutorObserver | None = None,
    ) -> None:
        """
        :param build_directory: The directory in which all files generated durin the build should be stored.
        :param project_finder: This project finder should only search within the directory it was given, not
            around or in parent folders. Defaults to :class:`CurrentDirectoryProjectFinder`.
        :param executor: The executor to use when the graph is executed.
        :param observer: The executro observer to use when the graph is executed.
        """

        from kraken.core.executor.default import (
            DefaultGraphExecutor,
            DefaultPrintingExecutorObserver,
            DefaultTaskExecutor,
        )

        super().__init__()
        self.build_directory = build_directory
        self.project_finder = project_finder or CurrentDirectoryProjectFinder.default()
        self.executor = executor or DefaultGraphExecutor(DefaultTaskExecutor())
        self.observer = observer or DefaultPrintingExecutorObserver()
        self._finalized: bool = False
        self._root_project: Optional[Project] = None
        self._listeners: MutableMapping[ContextEvent.Type, list[ContextEvent.Listener]] = collections.defaultdict(list)

    @property
    def root_project(self) -> Project:
        assert self._root_project is not None, "Context.root_project is not set"
        return self._root_project

    @root_project.setter
    def root_project(self, project: Project) -> None:
        assert self._root_project is None, "Context.root_project is already set"
        self._root_project = project

    def load_project(
        self,
        directory: Path,
        parent: Project | None = None,
        require_buildscript: bool = True,
        runner: ScriptRunner | None = None,
        script: Path | None = None,
    ) -> Project:
        """Loads a project from a file or directory.

        :param directory: The directory to load the project from.
        :param parent: The parent project. If no parent is specified, then the :attr:`root_project`
            must not have been initialized yet and the loaded project will be initialize it.
            If the root project is initialized but no parent is specified, an error will be
            raised.
        :param require_buildscript: If set to `True`, a build script must exist in *directory*.
            Otherwise, it will be accepted if no build script exists in the directory.
        :param runner: If the :class:`ScriptRunner` for this project is already known, it can be passed here.
        :param script: If the script to load for the project is already known, it can be passed here. Cannot be
            specified without a *runner*.
        """

        from kraken.core.project import Project, ProjectLoaderError

        if not runner:
            if script is not None:
                raise ValueError("cannot specify `script` parameter without a `runner` parameter")
            project_info = self.project_finder.find_project(directory)
            if project_info is not None:
                script, runner = project_info
        if not script and runner:
            script = runner.find_script(directory)

        has_root_project = self._root_project is not None
        project = Project(directory.name, directory, parent, self)
        try:
            if parent:
                parent.add_child(project)

            self.trigger(ContextEvent.Type.on_project_init, project)

            with self.as_current(), project.as_current():
                if not has_root_project:
                    self._root_project = project

                if script is None and require_buildscript:
                    raise ProjectLoaderError(
                        project,
                        f"no buildscript found for {project} (directory: {project.directory.absolute().resolve()})",
                    )
                if script is not None:
                    assert runner is not None
                    runner.execute_script(script, {"project": project})

            self.trigger(ContextEvent.Type.on_project_loaded, project)

        except ProjectLoaderError as exc:
            if exc.project is project:
                # Revert changes if the project that the error occurred with is the current project.
                if not has_root_project:
                    self._root_project = None
                if parent:
                    parent.remove_child(project)
            raise

        return project

    def iter_projects(self, relative_to: Project | None = None) -> Iterator[Project]:
        """Iterates over all projects in the context."""

        def _recurse(project: Project) -> Iterator[Project]:
            yield project
            for child_project in project.subprojects().values():
                yield from _recurse(child_project)

        yield from _recurse(relative_to or self.root_project)

    def get_project(self, path: str, relative_to: Project | None = None) -> Project:
        """Resolve a project by its absolute or relative path.

        A path is a `:` separated string, where `:` represents the root project. Relative to the root project,
        a relative and absolute path will behave the same."""

        if path.startswith(":"):
            relative_to = self.root_project
            path = path[1:]
        else:
            relative_to = relative_to or self.root_project

        cumulative_path = relative_to.path
        for part in filter(None, path.split(":")):
            cumulative_path += ":" + part
            project = relative_to.subproject(part, load=False)
            if not project:
                raise ValueError(f"project {cumulative_path} does not exist")
            relative_to = project

        return relative_to

    def resolve_tasks(self, targets: list[str] | None, relative_to: Project | None = None) -> list[Task]:
        """Resolve the given project or task references in *targets* relative to the specified project, or by
        default relative to the root project. A target is a colon-separated string that behaves similar to a
        filesystem path to address projects and tasks in the hierarchy. The root project is represented with a
        single colon and cannot be referenced by its name.

        A target that is just a task name will match all tasks of that name."""

        relative_to = relative_to or self.root_project

        if targets is None:
            # Return all default tasks.
            return [
                task for project in self.iter_projects(relative_to) for task in project.tasks().values() if task.default
            ]

        tasks: list[Task] = []
        target: str

        for target in targets:

            # Target references followed by a question mark are optional, they are allowed to not resolve.
            optional = target.endswith("?")
            if optional:
                target = target[:-1]

            # Find the project to look for matching tasks in.
            project_ref, name = target.rpartition(":")[::2]
            project = self.get_project(project_ref, relative_to)

            # Find all matching tasks in all subprojects.
            matched_tasks = [
                task
                for project in self.iter_projects(project)
                for task in project.tasks().values()
                if task.name == name
            ]

            if not matched_tasks:
                if optional:
                    continue
                raise ValueError(f"task {target} does not exist")

            tasks += matched_tasks

        return tasks

    def finalize(self) -> None:
        """Call :meth:`Task.finalize()` on all tasks. This should be called before a graph is created."""

        if self._finalized:
            logger.warning("Context.finalize() called more than once", stack_info=True)
            return

        self._finalized = True
        self.trigger(ContextEvent.Type.on_context_begin_finalize, self)

        # Delegate to finalize calls in all tasks of all projects.
        for project in self.iter_projects():
            self.trigger(ContextEvent.Type.on_project_begin_finalize, project)
            for task in project.tasks().values():
                task.finalize()
            self.trigger(ContextEvent.Type.on_project_finalized, project)

        self.trigger(ContextEvent.Type.on_context_finalized, self)

    def get_build_graph(self, targets: Sequence[str | Task] | None) -> TaskGraph:
        """Returns the :class:`TaskGraph` that contains either all default tasks or the tasks specified with
        the *targets* argument.

        :param targets: A list of targets to resolve and to build the graph from.
        :raise ValueError: If not tasks were selected.
        """

        from kraken.core.graph import TaskGraph

        if targets is None:
            tasks = self.resolve_tasks(None)
        else:
            tasks = self.resolve_tasks([t for t in targets if isinstance(t, str)]) + [
                t for t in targets if not isinstance(t, str)
            ]

        if not tasks:
            raise ValueError("no tasks selected")

        graph = TaskGraph(self).trim(tasks)

        assert graph, "TaskGraph cannot be empty"
        return graph

    def execute(self, tasks: list[str | Task] | TaskGraph | None = None) -> None:
        """Execute all default tasks or the tasks specified by *targets* using the default executor.
        If :meth:`finalize` was not called already it will be called by this function before the build
        graph is created, unless a build graph is passed in the first place.

        :param tasks: The list of tasks to execute, or the build graph. If none specified, all default
            tasks will be executed.
        :raise BuildError: If any task fails to execute.
        """

        from kraken.core.graph import TaskGraph

        if isinstance(tasks, TaskGraph):
            assert self._finalized, "no, no, this is all wrong. you need to finalize the context first"
            graph = tasks
        else:
            if not self._finalized:
                self.finalize()
            graph = self.get_build_graph(tasks)

        self.executor.execute_graph(graph, self.observer)

        if not graph.is_complete():
            failed_tasks = list(graph.tasks(failed=True))
            if len(failed_tasks) == 1:
                message = f'task "{failed_tasks[0].path}" failed'
            else:
                message = "tasks " + ", ".join(f'"{task.path}"' for task in failed_tasks) + " failed"
            raise BuildError(message)

    @overload
    def listen(
        self, event_type: str | ContextEvent.Type
    ) -> Callable[[ContextEvent.T_Listener], ContextEvent.T_Listener]:
        ...

    @overload
    def listen(self, event_type: str | ContextEvent.Type, listener: ContextEvent.Listener) -> None:
        ...

    def listen(self, event_type: str | ContextEvent.Type, listener: ContextEvent.Listener | None = None) -> Any:
        """Registers a listener to the context for the given event type."""

        if isinstance(event_type, str):
            event_type = ContextEvent.Type[event_type]

        def register(listener: ContextEvent.T_Listener) -> ContextEvent.T_Listener:
            assert callable(listener), "listener must be callable, got: %r" % listener
            self._listeners[event_type].append(listener)
            return listener

        if listener is None:
            return register

        register(listener)

    def trigger(self, event_type: ContextEvent.Type, data: Any) -> None:
        assert isinstance(event_type, ContextEvent.Type), repr(event_type)
        assert event_type != ContextEvent.Type.any, "cannot trigger event of type 'any'"
        listeners = (*self._listeners.get(ContextEvent.Type.any, ()), *self._listeners.get(event_type, ()))
        for listener in listeners:
            # TODO(NiklasRosenstein): Should we catch errors in listeners of letting them propagate?
            listener(ContextEvent(event_type, data))


class BuildError(Exception):
    def __init__(self, failed_tasks: Iterable[str]) -> None:
        self.failed_tasks = set(failed_tasks)

    def __repr__(self) -> str:
        if len(self.failed_tasks) == 1:
            return f'task "{next(iter(self.failed_tasks))}" failed'
        else:
            return "tasks " + ", ".join(f'"{task}"' for task in sorted(self.failed_tasks)) + " failed"
