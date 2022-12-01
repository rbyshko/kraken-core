from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable

from nr.stream import Supplier  # For backwards compatibility with kraken-core<=0.10.13

Empty = Supplier.Empty  # For backwards compatibility with kraken-core<=0.10.13

__all__ = [
    "Supplier",
    "Empty",
]

if TYPE_CHECKING:
    from kraken.core.task import Task


class TaskSupplier(Supplier["Task"]):
    """Internal. This is a helper class that allows us to represent a dependency on a task in the lineage of a property
    without including an actual property of that task in it. This is a bit of a hack because the
    :meth:`Supplier.derived_from()` API only allows to return more suppliers."""

    def __init__(self, task: Task) -> None:
        self._task = task

    def get(self) -> Task:
        return self._task

    def derived_from(self) -> Iterable[Supplier[Any]]:
        return ()
