from __future__ import annotations

import copy
import dataclasses
import warnings
from pathlib import Path
from typing import Any, Callable, ClassVar, Iterable, Mapping, Sequence, TypeVar, cast

import typeapi
from kraken.common import NotSet
from nr.stream import Supplier

T = TypeVar("T")
U = TypeVar("U")


@dataclasses.dataclass
class PropertyConfig:
    """Used to annotate properties, to configure the property.

    .. code:: Example

        from kraken.core.property import Object, Property, output
        from typing_extensions import Annotated

        class MyObj(Object):
            a: Annotated[Property[int], PropertyConfig(output=True)]
    """

    output: bool = False
    default: Any | NotSet = NotSet.Value
    default_factory: Callable[[], Any] | NotSet = NotSet.Value


@dataclasses.dataclass
class PropertyDescriptor:
    name: str
    is_output: bool
    default: Any | NotSet
    default_factory: Callable[[], Any] | NotSet
    item_type: typeapi.Hint

    def has_default(self) -> bool:
        return not (self.default is NotSet.Value and self.default_factory is NotSet.Value)

    def get_default(self) -> Any:
        if self.default is not NotSet.Value:
            return copy.deepcopy(self.default)
        elif self.default_factory is not NotSet.Value:
            return self.default_factory()
        else:
            raise RuntimeError(f"property {self.name!r} has no default value")


class Property(Supplier[T]):
    """A property represents an input or output parameter of an :class:`Object`."""

    ValueAdapter = Callable[[Any], Any]

    # This dictionary is a registry for type adapters that are used to ensure that values passed
    # into a property with :meth:`set()` are of the appropriate type. If a type adapter for a
    # particular type does not exist, a basic type check is performed. Note that the type adaptation
    # is not particularly sophisticated at this point and will not apply on items in nested structures.
    VALUE_ADAPTERS: ClassVar[dict[type, ValueAdapter]] = {}

    @staticmethod
    def output() -> Any:
        """Assign the result of this function as a default value to a property on the class level of an :class:`Object`
        subclass to mark it as an output property. This is an alternative to using the :class:`typing.Annotated` type
        hint.

        .. code:: Example

            from kraken.core.property import Object, Property, output

            class MyObj(Object):
                a: Property[int] = output()
        """

        return PropertyConfig(output=True)

    @staticmethod
    def config(
        output: bool = False,
        default: Any | NotSet = NotSet.Value,
        default_factory: Callable[[], Any] | NotSet = NotSet.Value,
    ) -> Any:
        """Assign the result of this function as a default value to a property on the class level of an :class:`Object`
        subclass to configure it's default value or whether it is an output property. This is an alternative to using
        a :class:`typing.Annotated` type hint.

        .. code:: Example

            from kraken.core.property import Object, Property, config

            class MyObj(Object):
                a: Property[int] = config(default=42)
        """

        return PropertyConfig(output, default, default_factory)

    @staticmethod
    def default(value: Any) -> Any:
        """Assign the result of this function as a default value to a property to declare it's default value."""

        return PropertyConfig(False, value, NotSet.Value)

    @staticmethod
    def default_factory(func: Callable[[], Any]) -> Any:
        """Assign the result of this function as a default value to a property to declare it's default factory."""

        return PropertyConfig(False, NotSet.Value, func)

    def __init__(self, owner: Object, name: str, item_type: typeapi.Hint | Any) -> None:
        """
        :param owner: The object that owns the property instance.
        :param name: The name of the property.
        :param item_type: The original inner type hint of the property (excluding the Property type itself).
        """

        # Determine the accepted types of the property.
        item_type = item_type if isinstance(item_type, typeapi.Hint) else typeapi.of(item_type)
        if isinstance(item_type, typeapi.Union):
            # NOTE (NiklasRosenstein): We expect that any union member be just a type.
            accepted_types = [cast(typeapi.Type, t).type for t in item_type.types]
        elif isinstance(item_type, typeapi.Type):
            accepted_types = [item_type.type]
        else:
            raise RuntimeError(f"Property generic parameter must be a type or union, got {item_type}")

        # Ensure that we have value adapters for every accepted type.
        for accepted_type in accepted_types:
            if accepted_type not in self.VALUE_ADAPTERS:
                if not isinstance(accepted_type, type):
                    raise ValueError(f"missing value adapter for type {accepted_type!r}")
        assert len(accepted_types) > 0

        self.owner = owner
        self.name = name
        self.accepted_types = accepted_types
        self.item_type = item_type
        self._value: Supplier[T] = Supplier.void()
        self._derived_from: Sequence[Supplier[Any]] = ()
        self._finalized = False
        self._error_message: str | None = None

    def __repr__(self) -> str:
        try:
            owner_fmt = str(self.owner)
        except Exception:
            owner_fmt = type(self.owner).__name__ + "(<exception during fmt>)"
        return f"Property({owner_fmt}.{self.name})"

    def _adapt_value(self, value: Any) -> Any:
        errors = []
        for accepted_type in self.accepted_types:
            try:
                adapter = self.VALUE_ADAPTERS[accepted_type]
            except KeyError:
                if isinstance(accepted_type, type):
                    adapter = _type_checking_adapter(accepted_type)
                else:
                    raise
            try:
                return adapter(value)
            except TypeError as exc:
                errors.append(exc)
        raise TypeError(f"{self}: " + "\n".join(map(str, errors))) from (errors[0] if len(errors) == 1 else None)

    @property
    def value(self) -> Supplier[T]:
        return self._value

    def derived_from(self) -> Iterable[Supplier[Any]]:
        yield self._value
        yield from self._value.derived_from()
        yield from self._derived_from

    def get(self) -> T:
        try:
            return self._value.get()
        except Supplier.Empty:
            raise Supplier.Empty(self, self._error_message)

    def set(self, value: T | Supplier[T], derived_from: Iterable[Supplier[Any]] = ()) -> None:
        if self._finalized:
            raise RuntimeError(f"{self} is finalized")
        derived_from = list(derived_from)
        if not isinstance(value, Supplier):
            value = Supplier.of(self._adapt_value(value), derived_from)
            derived_from = ()
        self._value = value
        self._derived_from = derived_from

    def setcallable(self, func: Callable[[], T], derived_from: Iterable[Supplier[Any]] = ()) -> None:
        if self._finalized:
            raise RuntimeError(f"{self} is finalized")
        if not callable(func):
            raise TypeError('"func" must be callable')
        self._value = Supplier.of_callable(func, list(derived_from))
        self._derived_from = ()

    def setmap(self, func: Callable[[T], T]) -> None:
        if self._finalized:
            raise RuntimeError(f"{self} is finalized")
        if not callable(func):
            raise TypeError('"func" must be callable')
        self._value = self._value.map(func)

    def setdefault(self, value: T | Supplier[T]) -> None:
        if self._finalized:
            raise RuntimeError(f"{self} is finalized")
        if self._value.is_void():
            self.set(value)

    def setfinal(self, value: T | Supplier[T]) -> None:
        self.set(value)
        self.finalize()

    def seterror(self, message: str) -> None:
        """Set an error message that should be included when the property is read."""

        self._error_message = message

    def clear(self) -> None:
        self.set(Supplier.void())

    def finalize(self) -> None:
        """Prevent further modification of the value in the property."""

        if not self._finalized:
            self._finalized = True

    def provides(self, type_: type) -> bool:
        """Returns `True` if the property may provide an instance or a sequence of the given *type_*."""

        if isinstance(self.item_type, typeapi.Union):
            types = list(self.item_type.types)
        elif isinstance(self.item_type, typeapi.Type):
            types = [self.item_type]
        else:
            assert False, self.item_type

        for provided in types:
            if not isinstance(provided, typeapi.Type):
                continue
            if issubclass(provided.type, type_):
                return True
            if issubclass(provided.type, Sequence) and provided.args and len(provided.args) == 1:
                inner = provided.args[0]
                if isinstance(inner, typeapi.Type) and issubclass(inner.type, type_):
                    return True

        return False

    def get_of_type(self, type_: type[U]) -> list[U]:
        """Return the inner value or values of the property as a flat list of *t*. If the property returns only a
        a single value of the specified type, the returned list will contain only that value. If the property instead
        provides a sequence that contains one or more objects of the provided type, only those objects will be
        returned.

        Note that this does not work with generic parametrized types."""

        value = self.get()
        if type_ != object and isinstance(value, type_):
            return [value]
        if isinstance(value, Sequence):
            return [x for x in value if isinstance(x, type_)]
        if type_ == object:
            return [cast(U, value)]
        return []

    @staticmethod
    def value_adapter(type_: type) -> Callable[[ValueAdapter], ValueAdapter]:
        """Decorator for functions that serve as a value adapter for the given *type_*."""

        def decorator(func: Property.ValueAdapter) -> Property.ValueAdapter:
            Property.VALUE_ADAPTERS[type_] = func
            return func

        return decorator


class Object:
    """Base class. An object's schema is declared as annotations linking to properties."""

    __schema__: ClassVar[Mapping[str, PropertyDescriptor]] = {}

    def __init_subclass__(cls) -> None:
        """Initializes the :attr:`__schema__` by introspecting the class annotations."""

        schema: dict[str, PropertyDescriptor] = {}
        base: type[Object]
        for base in cls.__bases__:
            if issubclass(base, Object):
                schema.update(base.__schema__)

        for key, hint in typeapi.get_annotations(cls).items():
            hint = typeapi.of(hint)
            config: PropertyConfig | None = None

            # Unwrap annotatations, looking for a PropertyConfig annotation.
            if isinstance(hint, typeapi.Annotated):
                config = next((x for x in hint.metadata if isinstance(x, PropertyConfig)), None)
                hint = hint.wrapped

            # Check if :func:`output()` or :func:`default()` was used to configure the property.
            if hasattr(cls, key) and isinstance(getattr(cls, key), PropertyConfig):
                assert config is None, "PropertyConfig cannot be on both an attribute and type annotation"
                config = getattr(cls, key)
                delattr(cls, key)

            # Is the hint pointing to a Property type?
            if isinstance(hint, typeapi.Type) and hint.type == Property:
                assert isinstance(hint, typeapi.Type) and hint.type == Property, hint
                assert hint.args is not None and len(hint.args) == 1, hint
                config = config or PropertyConfig()
                schema[key] = PropertyDescriptor(
                    name=key,
                    is_output=config.output,
                    default=config.default,
                    default_factory=config.default_factory,
                    item_type=hint.args[0],
                )

            # The attribute is annotated as an output but not actually typed as a property?
            elif config:
                raise RuntimeError(
                    f"Type hint for {cls.__name__}.{key} is annotated as a 'PropertyConfig', but not actually "
                    "typed as a 'Property'."
                )

            cls.__schema__ = schema

    def __init__(self) -> None:
        """Creates :class:`Properties <Property>` for every property defined in the object's schema."""

        for key, desc in self.__schema__.items():
            prop = Property[Any](self, key, desc.item_type)
            setattr(self, key, prop)
            if desc.has_default():
                prop.setdefault(desc.get_default())

    def update(self, _raise: bool = False, **property_values: Any) -> None:
        """Assign the properties in *property_values* to the properties of the given :class:`Object`. Raises a
        :class:`ValueError` if any of the properties in *property_values* are not in the objects' schema and if
        *_raise* is set to `True`. Prints a warning otherwise."""

        additional_keys = property_values.keys() - self.__schema__.keys()
        if additional_keys and _raise:
            raise ValueError(f"{type(self).__name__} does not have these properties: {additional_keys}")
        if additional_keys:
            self._warn_non_existent_properties(additional_keys)

        for key in property_values.keys() - additional_keys:
            prop: Property[Any] = getattr(self, key)
            if property_values[key] is None and not prop.provides(type(None)):
                continue
            prop.set(property_values[key])

    def _warn_non_existent_properties(self, keys: set[str]) -> None:
        warnings.warn(f"{type(self).__name__} does not have these properties: {keys}", UserWarning)


# Register common value adapters


def _type_checking_adapter(type_: type) -> Property.ValueAdapter:
    def func(value: Any) -> Any:
        if not isinstance(value, type_):
            raise TypeError(f"expected {type_.__name__}, got {type(value).__name__}")
        return value

    func.__name__ = f"check_{type_.__name__}"
    return func


@Property.value_adapter(Path)
def _adapt_path(value: Any) -> Path:
    if isinstance(value, str):
        return Path(value)
    if not isinstance(value, Path):
        raise TypeError(f"expected Path, got {type(value).__name__}")
    return value
