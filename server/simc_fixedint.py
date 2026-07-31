"""Minimal drop-in integer type required by SimC's isolated Salsa20 reader."""

from __future__ import annotations

from typing import Any


class MutableUInt32:
    """Mutable unsigned integer with wraparound at 32 bits."""

    def __init__(self, value: Any = 0) -> None:
        self._value = self._coerce(value) & 0xFFFFFFFF

    @staticmethod
    def _coerce(value: Any) -> int:
        if isinstance(value, MutableUInt32):
            return value._value
        return int(value)

    @classmethod
    def from_bytes(
        cls,
        value: bytes,
        byteorder: str,
    ) -> "MutableUInt32":
        return cls(int.from_bytes(value, byteorder, signed=False))

    def to_bytes(self, length: int, byteorder: str) -> bytes:
        return self._value.to_bytes(length, byteorder, signed=False)

    def __int__(self) -> int:
        return self._value

    def __index__(self) -> int:
        return self._value

    def __eq__(self, other: Any) -> bool:
        try:
            return self._value == self._coerce(other)
        except (TypeError, ValueError):
            return False

    def __add__(self, other: Any) -> "MutableUInt32":
        return MutableUInt32(self._value + self._coerce(other))

    def __radd__(self, other: Any) -> "MutableUInt32":
        return self + other

    def __iadd__(self, other: Any) -> "MutableUInt32":
        self._value = (
            self._value + self._coerce(other)
        ) & 0xFFFFFFFF
        return self

    def __xor__(self, other: Any) -> "MutableUInt32":
        return MutableUInt32(self._value ^ self._coerce(other))

    def __rxor__(self, other: Any) -> "MutableUInt32":
        return self ^ other

    def __ixor__(self, other: Any) -> "MutableUInt32":
        self._value = (
            self._value ^ self._coerce(other)
        ) & 0xFFFFFFFF
        return self

    def __lshift__(self, count: int) -> "MutableUInt32":
        return MutableUInt32(self._value << count)

    def __rshift__(self, count: int) -> "MutableUInt32":
        return MutableUInt32(self._value >> count)

    def __or__(self, other: Any) -> "MutableUInt32":
        return MutableUInt32(self._value | self._coerce(other))

    def __ror__(self, other: Any) -> "MutableUInt32":
        return self | other
