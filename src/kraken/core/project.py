import warnings

from .system.project import Project, ProjectLoaderError

warnings.warn(
    "The `kraken.core.project` module is deprecated; you should import only public API from `kraken.core.api` instead.",
    DeprecationWarning,
)

__all__ = [
    "ProjectLoaderError",
    "Project",
]
