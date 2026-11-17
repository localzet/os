#!/usr/bin/env python3
"""Collect a review inventory, not a redistribution or licensing verdict."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess

PACKAGE = re.compile(r"[a-z0-9][a-z0-9+.-]+")
ARCH = re.compile(r"[a-z0-9][a-z0-9-]*")
VERSION = re.compile(r"[0-9A-Za-z.+:~\-]+")
FORMAT = (
    "${binary:Package}\\t${Package}\\t${Version}\\t${Architecture}\\t"
    "${source:Package}\\t${source:Version}\\t${db:Status-Abbrev}\\n"
)


def notice(root: Path, package: str, binary: str) -> dict:
    # Multiarch packages may use a qualified doc directory. Relative links
    # within the target rootfs are fine; never read through an escaping link.
    for name in dict.fromkeys((binary, package)):
        candidate = root / "usr/share/doc" / name / "copyright"
        try:
            path = candidate.resolve(strict=True)
        except (FileNotFoundError, RuntimeError):
            continue
        if not path.is_relative_to(root):
            return {"status": "escaping-link", "path": str(candidate.relative_to(root))}
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            return {"status": "not-regular", "path": str(candidate.relative_to(root))}
        if not 0 < info.st_size <= 16 * 1024 * 1024:
            return {"status": "empty-or-oversized", "path": str(candidate.relative_to(root))}
        with path.open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        return {"status": "present-unreviewed", "path": str(candidate.relative_to(root)),
                "resolved_path": str(path.relative_to(root)), "sha256": checksum,
                "size": info.st_size}
    return {"status": "missing"}


def parse_packages(output: str) -> list[dict]:
    packages = []
    seen = set()
    for line in output.splitlines():
        fields = line.split("\t")
        if len(fields) != 7:
            raise ValueError("Malformed dpkg-query record")
        binary, package, version, arch, source, source_version, state = fields
        if not (PACKAGE.fullmatch(package) and PACKAGE.fullmatch(source)
                and ARCH.fullmatch(arch) and VERSION.fullmatch(version)
                and VERSION.fullmatch(source_version)
                and binary in (package, f"{package}:{arch}")):
            raise ValueError(f"Unexpected dpkg-query metadata: {binary!r}")
        # dpkg-query also reports residual configuration and partial states.
        # A prepared release root must contain only fully installed packages.
        if state != "ii ":
            raise ValueError(f"Non-installed or inconsistent package state: {binary} {state!r}")
        if binary in seen:
            raise ValueError(f"Duplicate binary package: {binary}")
        seen.add(binary)
        packages.append({"binary": binary, "package": package, "version": version,
                         "architecture": arch, "source_package": source,
                         "source_version": source_version})
    if not packages:
        raise ValueError("No installed package records")
    return sorted(packages, key=lambda row: row["binary"])


def collect(root: Path, manifest: Path) -> dict:
    root = root.resolve(strict=True)
    if root == Path("/") or not root.is_dir():
        raise ValueError("Use a prepared disposable rootfs, not the host")
    admin = root / "var/lib/dpkg"
    if not admin.resolve(strict=True).is_relative_to(root):
        raise ValueError("dpkg database escapes rootfs")
    status = admin / "status"
    if not status.is_file() or status.is_symlink():
        raise ValueError("Missing regular dpkg status database")
    output = subprocess.check_output(
        ["dpkg-query", f"--admindir={admin}", "-W", f"-f={FORMAT}"],
        text=True, timeout=120,
    )
    packages = parse_packages(output)
    # Existing ISO assembly embeds Package + Version in this exact format.
    # Compare multiplicities, preserving multiarch records with equal versions.
    if not manifest.is_file() or manifest.is_symlink():
        raise ValueError("Expected an extracted regular filesystem.manifest")
    data = manifest.read_bytes()
    rows = Counter()
    for line in data.decode("utf-8").splitlines():
        fields = line.split(" ")
        if len(fields) != 2 or not PACKAGE.fullmatch(fields[0]) or not VERSION.fullmatch(fields[1]):
            raise ValueError("Malformed ISO filesystem.manifest")
        rows[tuple(fields)] += 1
    expected = Counter((row["package"], row["version"]) for row in packages)
    if rows != expected:
        raise ValueError("Rootfs dpkg inventory differs from ISO filesystem.manifest")
    for row in packages:
        row["copyright"] = notice(root, row["package"], row["binary"])
    missing = [row["binary"] for row in packages
               if row["copyright"]["status"] != "present-unreviewed"]
    return {"schema": 1, "status": "review-required",
            "filesystem_manifest_sha256": hashlib.sha256(data).hexdigest(),
            "package_count": len(packages), "copyright_review_required": missing,
            "redistribution_approved": False, "packages": packages}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rootfs", type=Path)
    parser.add_argument("--iso-manifest", required=True, type=Path,
                        help="filesystem.manifest extracted from the exact built ISO")
    args = parser.parse_args()
    try:
        report = collect(args.rootfs, args.iso_manifest)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Inventory failed: {exc}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
