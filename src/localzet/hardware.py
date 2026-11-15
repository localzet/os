"""Read-only hardware inventory and conditional driver plan.

No package installation, network access, firmware writes or module loading.
PCI IDs are evidence of a device, not proof of driver/CUDA compatibility.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class PCIDevice:
    address: str
    vendor: str
    device: str
    device_class: str
    driver: str | None


def _hex(path: Path, digits: int) -> str:
    value = path.read_text(encoding="ascii").strip().lower()
    if not re.fullmatch(r"0x[0-9a-f]{" + str(digits) + "}", value):
        raise ValueError("Invalid PCI identifier")
    return value[2:]


def inventory(root: Path = Path("/sys/bus/pci/devices")) -> tuple[PCIDevice, ...]:
    rows = []
    for path in sorted(root.iterdir()):
        if not re.fullmatch(r"[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]", path.name):
            continue
        # Devices can disappear during enumeration (hotplug). Do not turn an
        # unreadable device into a positive hardware match.
        try:
            vendor, device = _hex(path / "vendor", 4), _hex(path / "device", 4)
            cls = _hex(path / "class", 6)
            driver_link = path / "driver"
            driver = driver_link.readlink().name if driver_link.is_symlink() else None
            rows.append(PCIDevice(path.name, vendor, device, cls, driver))
        except (OSError, UnicodeError, ValueError):
            continue
    return tuple(rows)


def plan(devices: tuple[PCIDevice, ...]) -> dict:
    graphics = tuple(row for row in devices if row.device_class.startswith("03"))
    nvidia = tuple(row for row in graphics if row.vendor == "10de")
    amd = tuple(row for row in graphics if row.vendor == "1002")
    intel = tuple(row for row in graphics if row.vendor == "8086")
    # NVIDIA audio/USB/bridge functions are not GPUs. GPU detection alone
    # does not select a driver series or prove CUDA compute support.
    tasks = [
        {"id": "firmware-microcode", "status": "review", "reason": "Review CPU and missing firmware against signed Ubuntu archive"},
        {"id": "additional-drivers", "status": "review", "reason": "Resolve actual modaliases using Ubuntu driver tooling"},
    ]
    if nvidia:
        tasks.extend((
            {"id": "nvidia-driver", "status": "review", "reason": "Resolve recommended compatible signed driver; no hard-coded series"},
            {"id": "cuda-toolkit", "status": "conditional", "reason": "Auto-select after GPU architecture, driver, CUDA and archive compatibility checks"},
            {"id": "nvidia-container-toolkit", "status": "conditional", "reason": "Complete profile, verified NVIDIA compute and opted-in Docker GPU support"},
        ))
    if amd or intel:
        tasks.append({"id": "mesa-vulkan", "status": "review", "reason": "Verify kernel DRM driver, Mesa, Vulkan and optional 32-bit graphics libraries"})
    return {"schema": 1, "mode": "read-only", "install_ready": False,
            "graphics": [asdict(row) for row in graphics],
            "nvidia_gpu_detected": bool(nvidia),
            "hybrid_graphics_candidate": len(graphics) > 1,
            "unbound_pci_devices": [asdict(row) for row in devices if row.driver is None],
            "tasks": tasks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        devices = inventory()
    except OSError as error:
        parser.exit(1, f"Hardware inventory unavailable: {error}\n")
    print(json.dumps(plan(devices), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
