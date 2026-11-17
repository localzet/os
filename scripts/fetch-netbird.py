#!/usr/bin/env python3
"""Fetch and inspect the exact official NetBird DEBs; never run scripts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://github.com/netbirdio/netbird/releases/download"
SCRIPTS = {"preinst", "postinst", "prerm", "postrm", "config", "triggers"}
PACKAGES = ("netbird", "netbird-ui")


def spec(manifest, package):
    if (manifest.get("schema") != 1 or manifest.get("project") != "netbirdio/netbird"
            or manifest.get("status") != "engineering-review" or package not in PACKAGES):
        raise ValueError("Unexpected NetBird package manifest")
    version = manifest["version"]
    if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Invalid version")
    asset = manifest["assets"][package]
    if (asset["name"] != f"{package}_{version}_linux_amd64.deb"
            or type(asset["size"]) is not int or not 0 < asset["size"] < 100 * 1024**2
            or not re.fullmatch(r"[0-9a-f]{64}", asset["sha256"])
            or not set(asset["scripts"]) <= SCRIPTS
            or any(not re.fullmatch(r"[0-9a-f]{40}", value) for value in asset["scripts"].values())):
        raise ValueError("Invalid pinned NetBird metadata")
    return f"{BASE}/v{version}/{asset['name']}", asset


def git_blob_id(data):
    # This is source comparison only. Artifact integrity is SHA-256.
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def verify(path, manifest, package):
    _, asset = spec(manifest, package)
    if path.stat().st_size != asset["size"]:
        raise ValueError("Package size mismatch")
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != asset["sha256"]:
            raise ValueError("Package SHA-256 mismatch")
    for field, expected in (("Package", package), ("Version", manifest["version"]), ("Architecture", "amd64")):
        actual = subprocess.check_output(["/usr/bin/dpkg-deb", "-f", str(path), field], text=True).strip()
        if actual != expected:
            raise ValueError("Unexpected package " + field + ": " + actual)
    with tempfile.TemporaryDirectory() as directory:
        subprocess.run(["/usr/bin/dpkg-deb", "-e", str(path), directory], check=True)
        scripts = {p.name: git_blob_id(p.read_bytes()) for p in Path(directory).iterdir() if p.name in SCRIPTS}
        if scripts != asset["scripts"]:
            raise ValueError("Maintainer scripts differ from reviewed tagged source: " + repr(scripts))


def fetch(manifest, package, destination):
    url, asset = spec(manifest, package)
    target = destination / asset["name"]
    if target.exists() or target.is_symlink():
        raise ValueError("Refusing existing destination")
    with tempfile.TemporaryDirectory(dir=destination) as directory:
        staged = Path(directory) / "asset"
        subprocess.run(["/usr/bin/curl", "--fail", "--silent", "--show-error", "--location",
                        "--proto", "=https", "--proto-redir", "=https", "--connect-timeout", "20",
                        "--max-time", "300", "--max-filesize", str(asset["size"]), "--output", str(staged), url],
                       check=True)
        verify(staged, manifest, package)
        os.link(staged, target)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    manifest = json.loads((ROOT / "config/upstream/netbird.json").read_text())
    args.directory.mkdir(parents=True, exist_ok=True)
    for package in PACKAGES:
        print(fetch(manifest, package, args.directory))


if __name__ == "__main__":
    main()
