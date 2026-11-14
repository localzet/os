#!/usr/bin/env python3
"""Fetch only the reviewed, pinned official release assets. Never execute."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://github.com/ONLYOFFICE/DesktopEditors/releases/download"
NAMES = {"deb": "onlyoffice-desktopeditors_amd64.deb", "appimage": "DesktopEditors-x86_64.AppImage"}


def spec(manifest, kind):
    if (manifest.get("schema") != 1 or manifest.get("project") != "ONLYOFFICE/DesktopEditors"
            or manifest.get("status") != "engineering-review"):
        raise ValueError("Invalid official artifact manifest")
    version = manifest["version"]
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) or manifest["tag"] != "v" + version:
        raise ValueError("Invalid release version")
    asset = manifest["artifacts"][kind]
    if (asset["name"] != NAMES[kind] or type(asset["size"]) is not int
            or not 0 < asset["size"] <= 1024**3
            or not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"])):
        raise ValueError("Invalid pinned asset metadata")
    return f"{BASE}/{manifest['tag']}/{asset['name']}", asset


def verify(path, asset):
    if path.stat().st_size != asset["size"]:
        raise ValueError("Artifact size mismatch")
    with path.open("rb") as f:
        if hashlib.file_digest(f, "sha256").hexdigest() != asset["sha256"]:
            raise ValueError("Artifact SHA-256 mismatch")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=tuple(NAMES))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    url, asset = spec(json.loads((ROOT / "config/upstream/onlyoffice.json").read_text()), args.kind)
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / asset["name"]
    if destination.exists() or destination.is_symlink():
        parser.error("Refusing to overwrite an existing artifact")
    with tempfile.TemporaryDirectory(dir=directory) as temp:
        staged = Path(temp) / "asset"
        subprocess.run(["curl", "--fail", "--silent", "--show-error", "--location",
                        "--proto", "=https", "--proto-redir", "=https",
                        "--connect-timeout", "20", "--max-time", "600",
                        "--max-filesize", str(asset["size"]), "--output", str(staged), url],
                       check=True)
        verify(staged, asset)
        # Atomic no-overwrite publication, same filesystem.
        os.link(staged, destination)
    print(destination)


if __name__ == "__main__":
    main()
