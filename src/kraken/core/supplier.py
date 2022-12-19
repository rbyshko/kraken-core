import warnings

from nr.stream import Supplier  # For backwards compatibility with kraken-core<=0.10.13

from .system.task_supplier import TaskSupplier

Empty = Supplier.Empty  # For backwards compatibility with kraken-core<=0.10.13

warnings.warn(
    "The `kraken.core.supplier` module is deprecated; you should import only public API from `kraken.core.api` instead.",  # noqa: E501
    DeprecationWarning,
)

__all__ = [
    "Empty",
    "Supplier",
    "TaskSupplier",
]
