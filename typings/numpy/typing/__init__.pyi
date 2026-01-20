from typing import Any, Generic, TypeVar
from .. import ndarray

_DType = TypeVar("_DType")
class NDArray(Generic[_DType], ndarray): ...
