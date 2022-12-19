import warnings

from .system.property import Object, Property, PropertyConfig, PropertyDescriptor

warnings.warn(
    "The `kraken.core.property` module is deprecated; you should import only public API from `kraken.core.api` instead.",  # noqa: E501
    DeprecationWarning,
)

__all__ = [
    "Object",
    "Property",
    "PropertyConfig",
    "PropertyDescriptor",
]
