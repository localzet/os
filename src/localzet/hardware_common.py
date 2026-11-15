"""Conservative general hardware baseline, using Ubuntu archive packages only."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import platform
import subprocess

from localzet.hardware import inventory, plan, secure_boot, simulate_packages

MICROCODE = {"GenuineIntel": "intel-microcode", "AuthenticAMD": "amd64-microcode"}


def cpu_vendor(path=Path("/proc/cpuinfo")):
    try:
        vendors = {line.split(":", 1)[1].strip() for line in path.read_text().splitlines()
                   if ":" in line and line.split(":", 1)[0].strip() == "vendor_id"}
        return next(iter(vendors)) if len(vendors) == 1 else "unknown"
    except OSError:
        return "unknown"


def physical_cpu():
    try:
        result = subprocess.run(["/usr/bin/systemd-detect-virt", "--vm", "--quiet"],
                                timeout=5, check=False, capture_output=True)
        return result.returncode == 1
    except (OSError, subprocess.SubprocessError):
        return False


def common_targets(devices, vendor, physical):
    # Ubuntu 26.04 linux-firmware depends on its split vendor packages.
    # No guessing USB/PCI firmware filenames or downloading arbitrary blobs.
    names = ["linux-firmware"]
    if physical and vendor in MICROCODE:
        names.append(MICROCODE[vendor])
    if any(row.vendor in ("1002", "8086") and row.device_class.startswith("03")
           for row in devices):
        names.extend(("libgl1-mesa-dri", "mesa-vulkan-drivers"))
    return tuple(names)


def review_common(cache):
    devices = inventory()
    vendor = cpu_vendor()
    physical = physical_cpu()
    targets = common_targets(devices, vendor, physical)
    transaction = simulate_packages(cache, targets, retain_marks=True)
    if transaction["status"] != "simulated":
        raise ValueError("General hardware transaction blocked: " + transaction["status"])
    try:
        for change in transaction["changes"]:
            name = change["name"].split(":")[0]
            if ((name.startswith("linux-") and not name.startswith("linux-firmware"))
                or name.startswith(("nvidia-driver-", "nvidia-dkms-", "nvidia-kernel-",
                                    "nvidia-utils-", "libnvidia-", "cuda-", "grub", "shim"))
                or name in ("dkms", "dracut", "nvidia-prime", "cuda")):
                raise ValueError("General hardware setup would change kernel/driver/bootloader: " + name)
        return {"phase": "base", "runtime": [{"cpu_vendor": vendor, "physical_cpu": physical}],
                "kernel": platform.release(), "secure_boot": secure_boot(),
                "graphics": plan(devices)["graphics"], "targets": list(targets),
                "target_versions": {name: cache[name].candidate.version for name in targets},
                "changes": transaction["changes"],
                "download_bytes": transaction["download_bytes"],
                "additional_installed_bytes": transaction["additional_installed_bytes"]}
    except BaseException:
        cache.clear()
        raise
