import warnings

from .system.task import (
    BackgroundTask,
    GroupTask,
    Task,
    TaskRelationship,
    TaskSet,
    TaskSetPartitions,
    TaskSetSelect,
    TaskStatus,
    TaskStatusType,
    VoidTask,
)

warnings.warn(
    "The `kraken.core.task` module is deprecated; you should import only public API from `kraken.core.api` instead.",
    DeprecationWarning,
)

__all__ = [
    "TaskStatusType",
    "TaskStatus",
    "Task",
    "GroupTask",
    "VoidTask",
    "BackgroundTask",
    "TaskSet",
    "TaskSetSelect",
    "TaskSetPartitions",
    "TaskRelationship",
]
