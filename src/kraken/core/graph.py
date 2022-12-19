import warnings

from .system.graph import TaskGraph, _Edge

warnings.warn(
    "The `kraken.core.graph` module is deprecated; you should import only public API from `kraken.core.api` instead.",
    DeprecationWarning,
)

__all__ = [
    "_Edge",
    "TaskGraph",
]
