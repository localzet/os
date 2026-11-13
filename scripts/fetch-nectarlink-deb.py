#!/usr/bin/env python3
"""Download and inspect the pinned upstream DEB; never install or execute it."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
import tomllib
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "packaging/nectarlink/release.toml"
MAX_BYTES = 512 * 1024 * 1024


def verify_package(path: Path, release: dict) -> None:
    with path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    if digest != release["deb_sha256"]:
        raise ValueError("DEB SHA-256 mismatch")
    for field, key in (("Package", "package"), ("Version", "version"),
                       ("Architecture", "architecture")):
        value = subprocess.check_output(
            ["dpkg-deb", "--field", str(path), field], text=True, timeout=30
        ).strip()
        if value != release[key]:
            raise ValueError(f"unexpected DEB {field}: {value}")


def load_release() -> dict:
    with LOCK.open("rb") as stream:
        release = tomllib.load(stream)
    version = release["version"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("invalid locked version")
    if release["package"] != "nectarlink" or release["architecture"] != "amd64":
        raise ValueError("unexpected locked package identity")
    expected = f"https://github.com/thtbee/nectarlink/releases/download/v{version}/nectarlink_{version}_amd64.deb"
    if release["deb_url"] != expected or not re.fullmatch(r"[0-9a-f]{64}", release["deb_sha256"]):
        raise ValueError("invalid pinned artifact")
    return release


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    release = load_release()
    args.output.mkdir(parents=True, exist_ok=True)
    filename = f"nectarlink_{release['version']}_amd64.deb"
    destination = args.output / filename
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    with tempfile.TemporaryDirectory(dir=args.output) as directory:
        candidate = Path(directory) / filename
        request = urllib.request.Request(release["deb_url"], headers={"User-Agent": "Localzet-OS-build"})
        with urllib.request.urlopen(request, timeout=60) as response, candidate.open("xb") as target:
            if not response.geturl().startswith("https://"):
                raise ValueError("non-HTTPS artifact redirect")
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError("artifact exceeds size limit")
                target.write(chunk)
        verify_package(candidate, release)
        # Link fails if the final path has appeared concurrently.
        destination.hardlink_to(candidate)
    print(destination)
    print("Verified pinned artifact identity and SHA-256; not installed or approved for redistribution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
