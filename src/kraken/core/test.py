import warnings

from .testing import kraken_ctx, kraken_project

warnings.warn(
    "The `kraken.core.test` module is deprecated; you should import testing fixtures from `kraken.core.testing` instead.",  # noqa: E501
    DeprecationWarning,
)

__all__ = [
    "kraken_ctx",
    "kraken_project",
]
