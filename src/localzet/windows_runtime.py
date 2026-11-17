"""Localzet Windows Runtime prototype. Separate Wine prefixes are not sandboxes."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

WINE = Path("/usr/bin/wine")
PROFILE = re.compile(r"[a-z][a-z0-9-]{0,63}")
OLE_HEADER = bytes.fromhex("d0cf11e0a1b11ae1")
PE_ARCHITECTURES = {(0x014C, 0x010B): "x86", (0x8664, 0x020B): "x86-64"}


def launch_plan(file: Path, profile: str, data_home: Path) -> dict:
    if not PROFILE.fullmatch(profile):
        raise ValueError("Invalid profile: use lowercase letters, digits and hyphens")
    if not data_home.is_absolute():
        raise ValueError("Data home must be absolute")
    file = file.resolve(strict=True)
    if not file.is_file():
        raise ValueError("Select a regular local file")
    extension = file.suffix.lower()
    architecture = "msi-unknown"
    with file.open("rb") as stream:
        header = stream.read(64)
        if extension == ".exe":
            if len(header) != 64 or header[:2] != b"MZ":
                raise ValueError("Not a PE executable")
            offset = int.from_bytes(header[60:64], "little")
            if offset < 64 or offset > os.fstat(stream.fileno()).st_size - 26:
                raise ValueError("Invalid PE header offset")
            stream.seek(offset)
            pe = stream.read(26)
            if len(pe) != 26 or pe[:4] != b"PE\x00\x00":
                raise ValueError("Not a PE executable")
            machine = int.from_bytes(pe[4:6], "little")
            optional_size = int.from_bytes(pe[20:22], "little")
            magic = int.from_bytes(pe[24:26], "little")
            if optional_size < 2 or offset + 24 + optional_size > os.fstat(stream.fileno()).st_size:
                raise ValueError("Invalid PE optional header")
            architecture = PE_ARCHITECTURES.get((machine, magic))
            if architecture is None:
                raise ValueError("Unsupported PE architecture; only x86 and x86-64 are accepted")
            arguments = [str(WINE), str(file)]
        elif extension == ".msi" and header.startswith(OLE_HEADER):
            arguments = [str(WINE), "msiexec", "/i", str(file)]
        else:
            raise ValueError("Only PE .exe and OLE .msi candidates are accepted")
    prefix = data_home / "localzet" / "windows" / "prefixes" / profile
    return {"profile": profile, "prefix": str(prefix), "argv": arguments,
            "working_directory": str(file.parent), "architecture": architecture, "sandboxed": False,
            "compatibility_verified": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--run", action="store_true",
                        help="Explicitly execute trusted Windows code as your user")
    args = parser.parse_args(argv)
    try:
        data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
        plan = launch_plan(args.file, args.profile, data_home)
        if not args.run:
            print(json.dumps(plan, indent=2, ensure_ascii=False))
            return 0
        if os.geteuid() == 0:
            raise ValueError("Never execute Windows applications as root")
        if not WINE.is_file() or not os.access(WINE, os.X_OK):
            raise ValueError("Wine is not installed")
        prefix = Path(plan["prefix"])
        prefix.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if prefix.is_symlink():
            raise ValueError("Refusing symlinked Wine prefix")
        prefix.mkdir(exist_ok=True, mode=0o700)
        if not prefix.is_dir() or prefix.stat().st_uid != os.geteuid():
            raise ValueError("Wine prefix is not owned by the current user")
        env = os.environ.copy()
        env["WINEPREFIX"] = str(prefix)
        env.pop("WINEARCH", None)
        print("Warning: Wine is not a sandbox. Only run trusted programs.", file=sys.stderr, flush=True)
        return subprocess.call(plan["argv"], env=env, cwd=plan["working_directory"])
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Windows Runtime: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
