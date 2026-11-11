"""Read-only audit of a prepared installed rootfs, not a disk installer.

Fail closed if the extracted Live image still contains passwordless access,
autologin, debugging units or insecure Live-only session defaults.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


REQUIRED = ("etc/os-release", "etc/passwd", "etc/shadow")
LIVE_ONLY = (
    "etc/sudoers.d/90-localzet-live",
    "etc/systemd/system/localzet-boot-diagnostics.service",
    "etc/systemd/system/localzet-live-seat-guard.service",
    "usr/local/bin/localzet-boot-diagnostics",
)


def _safe_file(root: Path, relative: str) -> Path | None:
    path = root / relative
    if path.is_symlink():
        return None
    resolved = path.resolve(strict=False)
    if not resolved.is_relative_to(root):
        return None
    return path


def _read(root: Path, relative: str) -> str | None:
    path = _safe_file(root, relative)
    if path is None or not path.is_file():
        return None
    try:
        return path.read_text()
    except (OSError, UnicodeError):
        return None


def audit_installed_root(root: Path) -> dict[str, object]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("expected an extracted rootfs directory")
    problems: list[str] = []

    for relative in REQUIRED:
        if _read(root, relative) is None:
            problems.append(f"required file missing/unreadable: {relative}")

    for relative in LIVE_ONLY:
        if (root / relative).exists() or (root / relative).is_symlink():
            problems.append(f"Live-only artifact present: {relative}")

    # The temporary Live account must not survive installation even if its
    # home and sudo rule were removed and its password was locked.
    passwd = _read(root, "etc/passwd")
    if passwd is not None:
        for line in passwd.splitlines():
            if line.split(":", 1)[0] == "localzet":
                problems.append("temporary Live account remains in passwd")
                break

    shadow = _read(root, "etc/shadow")
    if shadow is not None:
        for line in shadow.splitlines():
            fields = line.split(":")
            # We do not reveal hashes. Only reject empty or otherwise
            # passwordless local accounts. Lock markers '!' and '*' allowed.
            if len(fields) >= 2 and fields[1] == "":
                problems.append(f"empty password for local account: {fields[0]}")

    gdm = _read(root, "etc/gdm3/custom.conf") or ""
    if re.search(r"(?im)^\s*AutomaticLoginEnable\s*=\s*True\s*$", gdm):
        problems.append("GDM automatic login still enabled")

    defaults = _read(root, "etc/dconf/db/localzet.d/00-defaults") or ""
    if re.search(r"(?im)^\s*lock-enabled\s*=\s*false\s*$", defaults):
        problems.append("Live-only screen lock disabled globally")
    if re.search(r"(?im)^\s*idle-delay\s*=\s*uint32\s+0\s*$", defaults):
        problems.append("Live-only idle timeout disabled globally")

    if (root / "home/localzet").exists():
        problems.append("Live user's home directory still present")

    return {
        "operation": "read_only_postinstall_audit",
        "safe_to_release": not problems,
        "problems": sorted(set(problems)),
        "writes_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Extracted installed rootfs directory")
    args = parser.parse_args()
    try:
        result = audit_installed_root(args.root)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Audit failed closed: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["safe_to_release"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
