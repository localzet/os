"""User-owned Windows application menu entries, never auto-executed."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from localzet.windows_runtime import launch_plan

ID = re.compile(r"[0-9a-f]{32}")
PREFIX = "com.localzet.WindowsApp."


def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")


def private_dir(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise ValueError("Shortcut directory must be owned by the user and not writable by others")


def atomic_write(path: Path, content: str, mode: int) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def clean_title(value: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 100 or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("Application name must contain 1–100 printable characters")
    return value.strip()


def identity(file: Path, profile: str) -> str:
    return sha256(os.fsencode(file) + b"\0" + profile.encode("ascii")).hexdigest()[:32]


class ShortcutStore:
    def __init__(self, root: Path | None = None):
        self.root = root if root is not None else data_home()
        if not self.root.is_absolute():
            raise ValueError("Data home must be absolute")
        self.records = self.root / "localzet/windows/shortcuts"
        self.apps = self.root / "applications"

    def _paths(self, key: str) -> tuple[Path, Path]:
        if not isinstance(key, str) or not ID.fullmatch(key):
            raise ValueError("Invalid shortcut identity")
        return self.records / (key + ".json"), self.apps / (PREFIX + key + ".desktop")

    def _read(self, key: str) -> dict:
        record, _ = self._paths(key)
        info = record.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_size > 8192:
            raise ValueError("Invalid shortcut file")
        data = json.loads(record.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != {"file", "profile", "title"}:
            raise ValueError("Invalid shortcut record")
        file = Path(data["file"])
        if not file.is_absolute() or file.suffix.lower() != ".exe":
            raise ValueError("Shortcut must refer to a local EXE")
        if identity(file, data["profile"]) != key:
            raise ValueError("Shortcut identity mismatch")
        clean_title(data["title"])
        return data

    def load(self, key: str) -> dict:
        data = self._read(key)
        plan = launch_plan(Path(data["file"]), data["profile"], self.root)
        if plan["architecture"] not in ("x86", "x86-64"):
            raise ValueError("Shortcut must refer to a valid Windows EXE")
        if Path(data["file"]).resolve(strict=True) != Path(data["file"]):
            raise ValueError("Shortcut target changed")
        return data

    def list(self) -> tuple[tuple[str, dict], ...]:
        if not self.records.exists():
            return ()
        private_dir(self.records)
        rows = []
        for path in sorted(self.records.glob("*.json")):
            try:
                rows.append((path.stem, self._read(path.stem)))
            except (OSError, ValueError, TypeError, KeyError):
                continue
        return tuple(sorted(rows, key=lambda row: row[1]["title"].casefold()))

    def save(self, file: Path, profile: str, title: str) -> str:
        file = file.resolve(strict=True)
        title = clean_title(title)
        plan = launch_plan(file, profile, self.root)
        if plan["architecture"] not in ("x86", "x86-64"):
            raise ValueError("Select an installed EXE, not the MSI installer")
        key = identity(file, profile)
        private_dir(self.records)
        private_dir(self.apps)
        record, desktop = self._paths(key)
        # A desktop entry contains no file path, shell fragment or user
        # arguments. Even a malicious name cannot inject an Exec field.
        name = title.replace("\\", "\\\\")
        entry = ("[Desktop Entry]\nType=Application\n"
                 f"Name={name}\n"
                 f"Exec=/usr/bin/localzet-windows --shortcut {key}\n"
                 "Icon=com.localzet.WindowsRuntime\nTerminal=false\n"
                 "Categories=Utility;\nStartupNotify=true\n")
        atomic_write(record, json.dumps({"file": str(file), "profile": profile, "title": title}, ensure_ascii=False) + "\n", 0o600)
        atomic_write(desktop, entry, 0o644)
        return key

    def remove(self, key: str) -> None:
        record, desktop = self._paths(key)
        # No Wine prefix, program file, or user documents are deleted.
        private_dir(self.records)
        private_dir(self.apps)
        self._read(key)
        desktop.unlink(missing_ok=True)
        record.unlink()
