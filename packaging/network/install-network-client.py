#!/usr/bin/python3
"""Privileged, fixed on-demand installation. No enrollment or proxy changes."""
import json
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
        run("/usr/bin/python3", "-I", str(ROOT / "scripts" / ("fetch-" + kind + ".py")), temp)
        packages = [str(directory / name) for name in filenames]
        for filename in packages:
            Path(filename).chmod(0o644)
        run("/usr/bin/apt-get", "-o", "Acquire::Retries=3", "-o", "APT::Get::AllowUnauthenticated=false", "update")
        run("/usr/bin/apt-get", "-o", "APT::Get::AllowUnauthenticated=false",
            "-y", "--no-remove", "--no-install-recommends", "install", *packages)
        if any(installed_version(name) != version for name, version in versions.items()):
            raise ValueError("Installed package version mismatch")
    print("Pinned client installed. Configure connection in its original UI.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print("Network installation failed:", exc, file=sys.stderr)
        raise SystemExit(2)
