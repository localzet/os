"""Read-only binding of a proposed SSD to a stable WWN or serial.

Never generates partition/format commands or authorizes any disk write.
"""
from __future__ import annotations
from hashlib import sha256
import json
from typing import Any
from localzet.installer.preflight import inspect_disk


class TargetSelectionError(ValueError):
    """Target is unsafe, unavailable, or not uniquely identified."""


def identity(device: dict[str, Any]) -> str | None:
    if device.get("type") != "disk":
        return None
    wwn = str(device.get("wwn") or "").strip()
    serial = str(device.get("serial") or "").strip()
    return f"wwn:{wwn}" if wwn else (f"serial:{serial}" if serial else None)


def read_only_target_plan(payload: dict[str, Any], selected_identity: str) -> dict[str, Any]:
    devices = payload.get("blockdevices")
    if not isinstance(devices, list):
        raise TargetSelectionError("lsblk must provide blockdevices")
    if not isinstance(selected_identity, str) or not selected_identity.startswith(("wwn:", "serial:")):
        raise TargetSelectionError("Select by WWN or serial, never by device path")
    if not selected_identity.split(":", 1)[1].strip():
        raise TargetSelectionError("Empty identity is not allowed")
    disks = [d for d in devices if d.get("type") == "disk"]
    ids = [identity(d) for d in disks]
    if ids.count(selected_identity) != 1:
        raise TargetSelectionError("Missing or ambiguous identity")
    index = ids.index(selected_identity)
    selected = inspect_disk(disks[index])
    if selected["status"] == "blocked":
        raise TargetSelectionError("Selected SSD is blocked: " + "; ".join(selected["blockers"]))
    descriptor = {
        "identity": selected_identity,
        "size_bytes": selected["size_bytes"],
        "model": selected["model"],
        "transport": selected["transport"],
    }
    fingerprint = sha256(json.dumps(descriptor, sort_keys=True).encode()).hexdigest()
    return {
        "operation": "read_only_target_plan",
        "selected_identity": selected_identity,
        "current_device_path_unstable": selected["path"],
        "hardware_fingerprint": fingerprint,
        "target": selected,
        "non_target_disks": [inspect_disk(d) for i, d in enumerate(disks) if i != index],
        "requires_revalidation_before_write": True,
        "requires_backup": True,
        "requires_destructive_confirmation": True,
        "install_ready": False,
        "write_operations_available": False,
        "warning": "Read-only plan is NOT permission to erase or install anything",
    }
