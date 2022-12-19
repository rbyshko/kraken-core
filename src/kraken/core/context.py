import warnings

from .system.context import BuildError, Context, ContextEvent, ContextEventType

warnings.warn(
    "The `kraken.core.context` module is deprecated; you should import only public API from `kraken.core.api` instead.",
    DeprecationWarning,
)

__all__ = [
    "Context",
    "BuildError",
    "ContextEvent",
    "ContextEventType",
]
