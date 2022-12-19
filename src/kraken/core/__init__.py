__version__ = "0.11.4"

# NOTE(NiklasRosenstein): Imports from `kraken.core` directly are deprecated; instead you should import
#   from `kraken.core.api`. This file will not be updated until the next release with breaking changes
#   which will completely clear the contents of the module.

from nr.stream import Supplier

from kraken.core.system.context import BuildError, Context, ContextEvent
from kraken.core.system.executor import Graph, GraphExecutor, GraphExecutorObserver
from kraken.core.system.graph import TaskGraph
from kraken.core.system.project import Project, ProjectLoaderError
from kraken.core.system.property import Property
from kraken.core.system.task import (
    BackgroundTask,
    GroupTask,
    Task,
    TaskRelationship,
    TaskSet,
    TaskStatus,
    TaskStatusType,
    VoidTask,
)

__all__ = [
    "BackgroundTask",
    "BuildError",
    "Context",
    "ContextEvent",
    "Graph",
    "GraphExecutor",
    "GraphExecutorObserver",
    "GroupTask",
    "Project",
    "ProjectLoaderError",
    "Property",
    "Supplier",
    "Task",
    "TaskGraph",
    "TaskRelationship",
    "TaskSet",
    "TaskStatus",
    "TaskStatusType",
    "VoidTask",
]
