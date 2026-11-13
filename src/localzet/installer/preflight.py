"""Read-only hardware inventory for Localzet OS installer development.

This code NEVER partitions, formats, mounts or writes a device. Its verdict
means 'safe to inspect manually', not 'safe to erase'. The eventual installer
must enforce its own independent policy before destructive operations.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any

LSBLK_COLUMNS = (
    "NAME,KNAME,PATH,TYPE,SIZE,RO,RM,ROTA,MODEL,SERIAL,WWN,TRAN,"
    "MOUNTPOINTS,FSTYPE,PTTYPE,PARTUUID,UUID,START"
)
MIN_SIZE_BYTES = 32 * 1024**3
PROTECTED_FILESYSTEMS = {
    "crypto_LUKS", "BitLocker", "LVM2_member", "linux_raid_member",
    "zfs_member", "swap",
}


def _flag(value: Any) -> bool | None:
    if value is True or value in (1, "1", "true", "True"):
        return True
    if value is False or value in (0, "0", "false", "False"):
        return False
    return None


def _descendants(device: dict[str, Any]):
    yield device
    for child in device.get("children") or []:
        yield from _descendants(child)


def _mounts(device: dict[str, Any]) -> list[str]:
    points = device.get("mountpoints")
    if not isinstance(points, list):
        points = [device.get("mountpoint")]
    return [str(p) for p in points if p and str(p) != "None"]


def inspect_disk(disk: dict[str, Any]) -> dict[str, Any]:
    """Classify an lsblk disk without authorizing any write operation."""
    blockers: list[str] = []
    warnings: list[str] = []
    nodes = list(_descendants(disk))
    path = disk.get("path")
    if disk.get("type") != "disk" or not isinstance(path, str) or not path.startswith("/dev/"):
        blockers.append("Not a recognised physical disk device")
    if _flag(disk.get("ro")) is not False:
        blockers.append("Read-only or unknown write-protection state")
    if str(disk.get("tran") or "").lower() == "usb":
        blockers.append("USB-attached device; external media excluded")
    if _flag(disk.get("rm")) is not False:
        blockers.append("Removable or unknown removable-media state")
    if _flag(disk.get("rota")) is not False:
        blockers.append("Rotational disk or SSD status unknown")
    try:
        size = int(disk.get("size") or 0)
    except (ValueError, TypeError):
        size = 0
    if size < MIN_SIZE_BYTES:
        blockers.append("Disk smaller than the 32 GiB minimum or size unknown")

    for node in nodes:
        name = str(node.get("name") or node.get("path") or "unknown")
        mounts = _mounts(node)
        if mounts:
            blockers.append(f"Mounted or active device {name}: {', '.join(mounts)}")
        if _flag(node.get("ro")) is True:
            blockers.append(f"Read-only device {name}")
        fs = node.get("fstype")
        if fs in PROTECTED_FILESYSTEMS:
            blockers.append(f"Protected filesystem on {name}: {fs}")
        if node is not disk and node.get("type") not in ("part",):
            blockers.append(f"Nested block device on {name}; manual review required")

    if len(nodes) > 1:
        warnings.append("Existing partitions are present and may contain data")
    if any(n.get("fstype") for n in nodes):
        warnings.append("Filesystem signatures detected; erasure would destroy data")
    warnings.append("Inventory is read-only; this does NOT authorize installation or erasure")
    # The installer must still show identity, partition list, and an explicit
    # confirmation in its own UI before any actual destructive operation.
    return {
        "path": path if isinstance(path, str) else None,
        "model": str(disk.get("model") or "").strip(),
        "serial": str(disk.get("serial") or "").strip(),
        "wwn": str(disk.get("wwn") or "").strip(),
        "size_bytes": size,
        "transport": disk.get("tran"),
        "rotational": _flag(disk.get("rota")),
        "partitions": max(0, len(nodes) - 1),
        "status": "blocked" if blockers else "manual_review_only",
        "blockers": blockers,
        "warnings": warnings,
    }


def inventory(payload: dict[str, Any]) -> dict[str, Any]:
    devices = payload.get("blockdevices")
    if not isinstance(devices, list):
        raise ValueError("lsblk JSON must contain a blockdevices list")
    return {
        "operation": "read_only_inventory",
        "writable_operations_available": False,
        "disks": [inspect_disk(d) for d in devices if d.get("type") == "disk"],
        "install_ready": False,
        "warning": "No disk can be erased or installed by this tool",
    }


def read_lsblk() -> dict[str, Any]:
    result = subprocess.run(
        ["lsblk", "--json", "--bytes", "--output", LSBLK_COLUMNS],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return json.loads(result.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Localzet OS disk inspection")
    parser.add_argument("--input", type=Path, help="Use a saved lsblk JSON fixture")
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text()) if args.input else read_lsblk()
        print(json.dumps(inventory(payload), ensure_ascii=False, indent=2))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"Disk inventory failed safely: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
