import warnings
from pathlib import Path

from .system.executor import Graph, GraphExecutor, GraphExecutorObserver

warnings.warn(
    "The `kraken.core.executor` module is deprecated; you should import only public API from `kraken.core.api` instead.",  # noqa: E501
    DeprecationWarning,
)

__all__ = [
    "Graph",
    "GraphExecutor",
    "GraphExecutorObserver",
]

# For full backwards compatibility, we'll allow importing the submodules of the original package here.
__path__ = [str(Path(__file__).parent / "system" / "executor")]
