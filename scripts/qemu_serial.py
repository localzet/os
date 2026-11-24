"""Helpers for exact readiness markers in QEMU serial output."""
import re


_ANSI_CONTROL_SEQUENCE = re.compile(
    rb"\x1b(?:"
    rb"\[[0-?]*[ -/]*[@-~]"
    rb"|\][^\x07]*(?:\x07|\x1b\\)"
    rb"|[PX^_][^\x1b]*(?:\x1b\\)"
    rb"|[@-_]"
    rb")"
)
_LINE_ENDINGS = re.compile(rb"\r\n?|\n")


def normalized_serial_lines(data: bytes) -> list[bytes]:
    """Remove ANSI sequences and normalize terminal line endings."""
    plain = _ANSI_CONTROL_SEQUENCE.sub(b"", data)
    return _LINE_ENDINGS.split(plain)


def has_serial_marker(data: bytes, marker: bytes) -> bool:
    """Match a complete normalized serial line, never a substring."""
    return any(line == marker for line in normalized_serial_lines(data))


def serial_integer(data: bytes, key: bytes) -> int | None:
    """Read a single integer from an exact KEY=value serial line."""
    prefix = key + b"="
    values = {
        line[len(prefix):]
        for line in normalized_serial_lines(data)
        if line.startswith(prefix) and line[len(prefix):].isdigit()
    }
    if len(values) != 1:
        return None
    return int(values.pop())
