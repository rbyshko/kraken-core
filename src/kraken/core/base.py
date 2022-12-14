from __future__ import annotations

import abc
import contextlib
from typing import Any, Callable, ClassVar, Generic, Iterator, List, Optional, TypeVar, cast, overload

from kraken.common import NotSet

T = TypeVar("T")
U = TypeVar("U")


class MetadataContainer:

    metadata: List[Any]

    def __init__(self) -> None:
        self.metadata = []

    @overload
    def find_metadata(self, of_type: type[T]) -> T | None:
        """Returns the first entry in the :attr:`metadata` that is of the specified type."""

    @overload
    def find_metadata(self, of_type: type[T], create: Callable[[], T]) -> T:
        """Returns the first entry in :attr:`metadata`, or creates one."""

    def find_metadata(self, of_type: type[T], create: Callable[[], T] | None = None) -> T | None:
        obj = next((x for x in self.metadata if isinstance(x, of_type)), None)
        if obj is None and create is not None:
            obj = create()
            self.metadata.append(obj)
        return obj


class CurrentProvider(abc.ABC, Generic[T]):
    @overload
    @classmethod
    def current(cls) -> T:
        """Returns the current context or raises a :class:`RuntimeError`."""

    @overload
    @classmethod
    def current(cls, fallback: U) -> T | U:
        """Returns the current context or *fallback*."""

    @classmethod
    def current(cls, fallback: U | NotSet = NotSet.Value) -> T | U:
        try:
            return cls._get_current_object()
        except RuntimeError:
            if isinstance(fallback, NotSet):
                raise
            return fallback

    @classmethod
    @abc.abstractmethod
    def _get_current_object(cls) -> T:
        raise NotImplementedError


class Currentable(CurrentProvider[T]):
    __current: ClassVar[Optional[Any]] = None  # note: ClassVar cannot contain type variables

    @classmethod
    def _get_current_object(cls) -> T:
        if cls.__current is None:
            raise RuntimeError(f"No current object for type `{cls.__name__}`")
        return cast(T, cls.__current)

    @contextlib.contextmanager
    def as_current(self) -> Iterator[None]:
        prev = type(self).__current
        try:
            type(self).__current = self
            yield
        finally:
            type(self).__current = prev
