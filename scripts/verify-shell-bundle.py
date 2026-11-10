#!/usr/bin/env python3
"""Validate a GNOME extension ZIP without extracting untrusted paths."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

UUID = "localzet-shell@localzet.com"
REQUIRED = {"metadata.json", "extension.js", "stylesheet.css"}
MAX_ARCHIVE_BYTES = 10 * 1024 * 1024

def validate(path: Path) -> str:
    if not path.is_file() or path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("bundle is missing or exceeds the 10 MiB limit")
    with zipfile.ZipFile(path) as bundle:
        names: set[str] = set()
        for member in bundle.infolist():
            name = member.filename
            parts = PurePosixPath(name).parts
            if (not parts or name.startswith("/") or "\\" in name
                    or any(part in (".", "..") for part in parts)
                    or member.is_dir() or len(parts) != 1 or name in names):
                raise ValueError(f"unsafe or duplicate archive entry: {name}")
            if stat.S_IFMT(member.external_attr >> 16) == stat.S_IFLNK:
                raise ValueError(f"symlink in archive: {name}")
            if member.flag_bits & 1:
                raise ValueError(f"encrypted archive entry: {name}")
            if member.file_size > MAX_ARCHIVE_BYTES:
                raise ValueError(f"oversized archive entry: {name}")
            names.add(name)
        if not REQUIRED.issubset(names):
            raise ValueError(f"missing extension files: {sorted(REQUIRED - names)}")
        metadata = json.loads(bundle.read("metadata.json"))
        if not isinstance(metadata, dict) or metadata.get("uuid") != UUID:
            raise ValueError("extension UUID does not match")
        versions = metadata.get("shell-version")
        if not isinstance(versions, list) or "50" not in versions:
            raise ValueError("GNOME Shell 50 is not declared")
        if not bundle.read("extension.js").strip():
            raise ValueError("extension.js is empty")
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        checksum = validate(args.bundle)
    except (ValueError, OSError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        parser.exit(1, f"Invalid Localzet Shell bundle: {error}\n")
    print(f"Verified {args.bundle.name}: SHA256 {checksum}")

if __name__ == "__main__":
    main()
