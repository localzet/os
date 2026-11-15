"""Conservative CUDA selection using a working NVIDIA driver and real PCI IDs."""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import io
import os
from pathlib import Path
import re
import subprocess

from localzet.hardware import PCIDevice, archive_candidate, inventory, simulate_packages


@dataclass(frozen=True)
class GPU:
    address: str
    capability: str
    driver_version: str


# Toolkit compiler targets, not a generic ">= compute capability" rule.
# NVIDIA CUDA 13.1.1 and 12.4.1 NVCC manuals and release notes.
TOOLKITS = (
    ("cuda-toolkit-13-1", "13.1", (590, 44, 1),
     frozenset(("7.5", "8.0", "8.6", "8.7", "8.8", "8.9", "9.0", "10.0", "10.3", "11.0", "12.0", "12.1"))),
    ("nvidia-cuda-toolkit", "12.4", (550, 54, 15),
     frozenset(("5.0", "5.2", "5.3", "6.0", "6.1", "6.2", "7.0", "7.2", "7.5", "8.0", "8.6", "8.7", "8.9", "9.0"))),
)


def parse_gpu_query(output: str) -> tuple[GPU, ...]:
    rows = []
    seen = set()
    for row in csv.reader(io.StringIO(output), skipinitialspace=True):
        if len(row) != 3:
            raise ValueError("Unexpected NVIDIA GPU query")
        bus, capability, version = (field.strip().lower() for field in row)
        if not re.fullmatch(r"(?:0000)?[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]", bus):
            raise ValueError("Invalid NVIDIA PCI address")
        bus = bus[-12:]
        if (bus in seen or not re.fullmatch(r"[0-9]{1,2}\.[0-9]", capability)
                or not re.fullmatch(r"[0-9]{3}\.[0-9]{1,3}\.[0-9]{1,3}", version)):
            raise ValueError("Invalid or duplicate NVIDIA GPU result")
        rows.append(GPU(bus, capability, version))
        seen.add(bus)
    if not rows:
        raise ValueError("NVIDIA driver did not report a GPU")
    return tuple(sorted(rows, key=lambda row: row.address))


def running_gpus(devices: tuple[PCIDevice, ...]) -> tuple[GPU, ...]:
    expected = {device.address: device for device in devices
                if device.vendor == "10de" and device.device_class.startswith("03")}
    if not expected or any(device.driver != "nvidia" for device in expected.values()):
        raise ValueError("All NVIDIA GPUs must be bound to the working NVIDIA driver")
    env = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "LC_ALL": "C.UTF-8"}
    try:
        proc = subprocess.run(["/usr/bin/nvidia-smi",
            "--query-gpu=pci.bus_id,compute_cap,driver_version", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True, timeout=15, env=env)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("NVIDIA driver runtime query failed; reboot or review the driver") from exc
    rows = parse_gpu_query(proc.stdout)
    if {row.address for row in rows} != set(expected) or len({row.driver_version for row in rows}) != 1:
        raise ValueError("NVIDIA runtime and PCI inventory disagree")
    return rows


def select_toolkit(gpus: tuple[GPU, ...], cache) -> str:
    if not gpus:
        raise ValueError("No verified NVIDIA GPU")
    for package, release, minimum, architectures in TOOLKITS:
        if not all(gpu.capability in architectures and
                   tuple(int(part) for part in gpu.driver_version.split(".")) >= minimum
                   for gpu in gpus):
            continue
        candidate = archive_candidate(cache, package)
        if candidate["status"] == "ubuntu-candidate" and re.match(
                r"^(?:[0-9]+:)?" + re.escape(release) + r"\.", candidate["version"]):
            return package
    raise ValueError("No reviewed CUDA toolkit matches every NVIDIA GPU and the running driver")


def cuda_transaction(cache, devices: tuple[PCIDevice, ...], *, retain_marks=False) -> dict:
    gpus = running_gpus(devices)
    package = select_toolkit(gpus, cache)
    try:
        transaction = simulate_packages(cache, (package,), retain_marks=retain_marks)
        if transaction["status"] != "simulated":
            raise ValueError("CUDA transaction is blocked: " + transaction["status"])
        # CUDA must not replace the working graphics stack or kernel.
        for change in transaction["changes"]:
            name = change["name"].split(":")[0]
            if name.startswith(("nvidia-driver-", "nvidia-dkms-", "nvidia-kernel-",
                    "nvidia-utils-", "nvidia-compute-utils-", "nvidia-headless-",
                    "libnvidia-", "xserver-xorg-video-nvidia-", "linux-", "cuda-drivers",
                    "libcuda1")) or name in ("dkms", "cuda", "nvidia-open", "nvidia-prime"):
                raise ValueError("CUDA would change the active driver or kernel: " + name)
        return {"runtime": [asdict(gpu) for gpu in gpus], "toolkit": package, "transaction": transaction}
    except BaseException:
        cache.clear()
        raise


def inspect_cuda(devices: tuple[PCIDevice, ...]) -> dict:
    try:
        import apt
        return {"status": "candidate", **cuda_transaction(apt.Cache(), devices),
                "install_ready": False}
    except (ImportError, OSError, RuntimeError, SystemError, ValueError) as error:
        return {"status": "blocked", "reason": str(error), "install_ready": False}
