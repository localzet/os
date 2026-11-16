#!/usr/bin/env python3
"""Verify original UserNet package, never execute its maintainer scripts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://github.com/localzet/UserNet/releases/download"
CONTROL = {"preinst", "postinst", "prerm", "postrm", "config", "triggers"}


def spec(manifest):
    if (manifest.get("schema") != 1 or manifest.get("project") != "localzet/UserNet"
            or manifest.get("status") != "engineering-review"):
        raise ValueError("Unexpected UserNet manifest")
    version, asset = manifest["version"], manifest["asset"]
    if (not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version)
            or not isinstance(manifest.get("deb_version"), str)
            or not re.fullmatch(re.escape(version) + r"\.\d{10}", manifest["deb_version"])
            or asset["name"] != "UserNet-linux.deb"
            or type(asset["size"]) is not int or not 0 < asset["size"] <= 256 * 1024**2
            or not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"])):
        raise ValueError("Invalid UserNet asset metadata")
    return f"{BASE}/v{version}/{asset['name']}", asset


def verify(path, manifest):
    _, asset = spec(manifest)
    if path.stat().st_size != asset["size"]:
        raise ValueError("Artifact size mismatch")
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != asset["sha256"]:
            raise ValueError("Artifact SHA-256 mismatch")
    for field, expected in (("Package", "usernet"), ("Version", manifest["deb_version"]), ("Architecture", "amd64")):
        actual = subprocess.check_output(["/usr/bin/dpkg-deb", "-f", str(path), field], text=True).strip()
        if actual != expected:
            raise ValueError("Unexpected UserNet package " + field + ": " + actual)


def fetch(manifest, destination):
    url, asset = spec(manifest)
    target = destination / asset["name"]
    if target.exists() or target.is_symlink():
        raise ValueError("Refusing existing destination")
    with tempfile.TemporaryDirectory(dir=destination) as directory:
        staged = Path(directory) / "asset"
        subprocess.run(["/usr/bin/curl", "--fail", "--silent", "--show-error", "--location",
                        "--proto", "=https", "--proto-redir", "=https", "--connect-timeout", "20",
                        "--max-time", "300", "--max-filesize", str(asset["size"]), "--output", str(staged), url],
                       check=True)
        verify(staged, manifest)
        os.link(staged, target)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    manifest = json.loads((ROOT / "config/upstream/usernet.json").read_text())
    args.directory.mkdir(parents=True, exist_ok=True)
    print(fetch(manifest, args.directory))


if __name__ == "__main__":
    main()
