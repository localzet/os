#!/usr/bin/python3
"""Privileged, fixed on-demand installation. No enrollment or proxy changes."""
import hashlib
import json
import shutil
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path("/opt/localzet-os")
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C.UTF-8",
       "HOME": "/root", "DEBIAN_FRONTEND": "noninteractive"}


def run(*argv, **kwargs):
    return subprocess.run(argv, env=ENV, check=True, **kwargs)


def installed_version(package):
    result = subprocess.run(["/usr/bin/dpkg-query", "-W", "-f=${Status}\t${Version}", package],
                            env=ENV, text=True, capture_output=True)
    if result.returncode == 0 and result.stdout.startswith("install ok installed\t"):
        return result.stdout.split("\t", 1)[1]
    return None


CACHE = Path("/usr/share/localzet/network-preload")


def cached_packages(kind, manifest, filenames, directory):
    """Use only a complete exact artifact set copied into private staging.

    SHA-256 pins cover all DEB data and reviewed maintainer scripts. Missing
    cache means the normal online path; damaged cache is a hard failure.
    """
    source = CACHE / kind
    if not source.exists():
        return False
    for name in filenames:
        asset = (next(item for item in manifest["assets"].values() if item["name"] == name)
                 if kind == "netbird" else manifest["asset"])
        if Path(name).name != name:
            raise ValueError("Invalid cache filename")
        file = source / name
        if not file.is_file() or file.is_symlink():
            raise ValueError("Incomplete network preload")
        destination = directory / name
        shutil.copyfile(file, destination)
        with destination.open("rb") as stream:
            if (destination.stat().st_size != asset["size"]
                    or hashlib.file_digest(stream, "sha256").hexdigest() != asset["sha256"]):
                raise ValueError("Network preload integrity mismatch")
        destination.chmod(0o644)
    return True


def offline_plan(plan, versions):
    """Refuse any removal, extra install or unexpected version/configure."""
    seen = set()
    for line in plan.splitlines():
        fields = line.split()
        if not fields:
            continue
        action = fields[0]
        if action in ("Remv", "Purg"):
            raise ValueError("Offline network plan would remove a package")
        if action not in ("Inst", "Conf"):
            continue
        match = re.fullmatch(r"(?:Inst|Conf) ([a-z0-9+.-]+)(?::(?:amd64|amd64v1|all))?(?: \[[^\]]+\])? \(([^ )]+).*\)(?: .*)?", line)
        if not match or versions.get(match[1]) != match[2]:
            raise ValueError("Offline network plan changed an unreviewed package: " + line)
        if action == "Inst":
            seen.add(match[1])
    if not seen:
        raise ValueError("Offline network plan contains no installation")
    return seen


def install_offline(packages, versions, runtime):
    # APT on Resolute fails on verified local DEBs with --no-download:
    # Internal Error, Pathname to install is not absolute. Resolve the
    # transaction using APT simulation, then use dpkg for only those exact
    # local files. dpkg cannot fetch missing dependencies.
    if any(not installed_version(package) for package in runtime):
        raise ValueError("Offline runtime dependencies missing")
    plan = run("/usr/bin/apt-get", "-o", "APT::Get::AllowUnauthenticated=false",
               "--simulate", "--no-remove", "--no-install-recommends", "install",
               *packages, text=True, capture_output=True).stdout
    offline_plan(plan, versions)
    for package, (name, version) in zip(packages, versions.items(), strict=True):
        for field, expected in (("Package", name), ("Version", version), ("Architecture", "amd64")):
            actual = run("/usr/bin/dpkg-deb", "-f", package, field,
                         text=True, capture_output=True).stdout.strip()
            if actual != expected:
                raise ValueError("Cached package metadata mismatch: " + field)
    run("/usr/bin/dpkg", "--no-act", "--install", *packages)
    run("/usr/bin/dpkg", "--install", *packages)
    run("/usr/bin/apt-get", "check")


def main():
    if (len(sys.argv) != 2 or sys.argv[1] not in ("netbird", "usernet")
            or os.geteuid() != 0 or not re.fullmatch(r"[1-9][0-9]*", os.environ.get("PKEXEC_UID", ""))):
        raise ValueError("Authenticated local administrator required")
    if "boot=casper" in Path("/proc/cmdline").read_text().split():
        raise ValueError("Install Localzet OS first; Live changes are not supported")
    if not any(line in ("ID=localzet", 'ID="localzet"') for line in Path("/etc/os-release").read_text().splitlines()):
        raise ValueError("Unsupported operating system")
    kind = sys.argv[1]
    manifest = json.loads((ROOT / "config/upstream" / (kind + ".json")).read_text())
    if kind == "netbird":
        versions = {name: manifest["version"] for name in ("netbird", "netbird-ui")}
        filenames = [manifest["assets"][name]["name"] for name in versions]
    else:
        versions = {"usernet": manifest["deb_version"]}
        filenames = [manifest["asset"]["name"]]
    existing = {name: installed_version(name) for name in versions}
    if all(existing[name] == version for name, version in versions.items()):
        print("Exact pinned client is already installed")
        return
    for name, current in existing.items():
        if current and subprocess.run(["/usr/bin/dpkg", "--compare-versions", current, "gt", versions[name]], env=ENV).returncode == 0:
            raise ValueError("Refusing to downgrade an installed network client")
    with tempfile.TemporaryDirectory(prefix="localzet-network-", dir="/var/tmp") as temp:
        directory = Path(temp)
        directory.chmod(0o755)
        offline = cached_packages(kind, manifest, filenames, directory)
        if not offline:
            run("/usr/bin/python3", "-I", str(ROOT / "scripts" / ("fetch-" + kind + ".py")), temp)
        packages = [str(directory / name) for name in filenames]
        for filename in packages:
            Path(filename).chmod(0o644)
        if not offline:
            run("/usr/bin/apt-get", "-o", "Acquire::Retries=3", "-o", "APT::Get::AllowUnauthenticated=false", "update")
        # The pinned UserNet DEB omits EGL from Depends. The real runtime
        # test exposed the missing library. Install archive-provided GL
        # dependencies without changing the NVIDIA driver selection.
        runtime = ["libegl1", "libegl-mesa0", "libgl1", "libgl1-mesa-dri", "libgles2"] if kind == "usernet" else []
        if offline:
            install_offline(packages, versions, runtime)
        else:
            run("/usr/bin/apt-get", "-o", "APT::Get::AllowUnauthenticated=false",
                "-y", "--no-remove", "--no-install-recommends", "install", *packages, *runtime)
        if any(installed_version(name) != version for name, version in versions.items()):
            raise ValueError("Installed package version mismatch")
    print("Pinned client installed. Configure connection in its original UI.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print("Network installation failed:", exc, file=sys.stderr)
        raise SystemExit(2)
