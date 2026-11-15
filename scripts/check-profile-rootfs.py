#!/usr/bin/env python3
"""Verify the actual archive packages in a disposable rootfs; no writes."""
import argparse
import json
from pathlib import Path
import subprocess

from localzet.profiles import load_manifest, plan


def verify(root, receipt):
    expected = plan(load_manifest(root / "opt/localzet-os/config/profiles.json"), receipt["profile"])
    if receipt != expected:
        raise ValueError("Unexpected or modified archive profile receipt")
    packages = receipt["ubuntu_package_candidates"]
    result = subprocess.run(
        ["chroot", str(root), "dpkg-query", "-W", "-f=${Package}\t${db:Status-Abbrev}\t${Version}\n", *packages],
        check=True, capture_output=True, text=True, timeout=30)
    installed = {}
    for line in result.stdout.splitlines():
        name, status, version = line.split("\t")
        if status != "ii " or not version or name in installed:
            raise ValueError(f"Package not fully installed: {name}")
        installed[name] = version
    if set(installed) != set(packages):
        raise ValueError("Installed package inventory differs from requested archive profile")
    return {"profile": receipt["profile"], "verified_archive_packages": installed,
            "pending_external_or_localzet": receipt["external_or_localzet_pending"],
            "browser_choice_pending": receipt["browser_choice_pending"],
            "complete_profile_ready": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    if root == Path("/") or not (root / "var/lib/dpkg/status").is_file():
        parser.error("Expected a disposable rootfs")
    print(json.dumps(verify(root, json.loads(args.receipt.read_text())), indent=2))


if __name__ == "__main__":
    main()
