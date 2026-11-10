"""Read-only system summary and module catalogue for Localzet Settings."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import platform
import shutil

from localzet.modules import Module, load_catalog


@dataclass(frozen=True)
class SystemInfo:
    system: str
    kernel: str
    architecture: str
    processors: str
    memory: str
    root_storage: str


def readable_bytes(value: int) -> str:
    if not isinstance(value, int) or value < 0:
        raise ValueError("byte count must be a nonnegative integer")
    for unit, scale in (("GiB", 1024**3), ("MiB", 1024**2), ("KiB", 1024)):
        if value >= scale:
            return f"{value / scale:.1f} {unit}"
    return f"{value} B"


def memory_total(meminfo: str) -> int | None:
    for line in meminfo.splitlines():
        if line.startswith("MemTotal:"):
            fields = line.split()
            if len(fields) != 3 or fields[2] != "kB":
                return None
            try:
                return int(fields[1]) * 1024
            except ValueError:
                return None
    return None


def system_info() -> SystemInfo:
    uname = platform.uname()
    try:
        memory = memory_total(Path("/proc/meminfo").read_text())
    except OSError:
        memory = None
    try:
        disk = shutil.disk_usage("/")
        storage = f"{readable_bytes(disk.free)} свободно из {readable_bytes(disk.total)}"
    except OSError:
        storage = "Недоступно"
    return SystemInfo(
        system="Localzet OS (Ubuntu-based)",
        kernel=uname.release,
        architecture=uname.machine,
        processors=str(os.cpu_count() or "Неизвестно"),
        memory=readable_bytes(memory) if memory is not None else "Недоступно",
        root_storage=storage,
    )


def load_modules(directory: Path) -> tuple[Module, ...]:
    """Describes capabilities, NOT whether they are installed or enabled."""
    return tuple(sorted(load_catalog(directory).values(), key=lambda x: x.title.casefold()))


def status_label(status: str) -> str:
    return {"planned": "В планах", "prototype": "Прототип", "supported": "Поддерживается"}.get(status, "Неизвестно")
