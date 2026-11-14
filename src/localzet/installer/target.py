"""Read-only binding of a proposed SSD to a stable WWN or serial.

Never generates partition/format commands or authorizes any disk write.
"""
from __future__ import annotations
from hashlib import sha256
import json
from typing import Any
from localzet.installer.preflight import inspect_disk, _flag


class TargetSelectionError(ValueError):
    """Target is unsafe, unavailable, or not uniquely identified."""


def identity(device: dict[str, Any]) -> str | None:
    if device.get("type") != "disk":
        return None
    wwn = str(device.get("wwn") or "").strip()
    serial = str(device.get("serial") or "").strip()
    return f"wwn:{wwn}" if wwn else (f"serial:{serial}" if serial else None)


def _layout(device: dict[str, Any]) -> dict[str, Any]:
    """Path-independent snapshot of the observed partition tree."""
    children = [_layout(child) for child in (device.get("children") or [])]
    children.sort(key=lambda item: json.dumps(item, sort_keys=True))
    return {
        "type": device.get("type"),
        "size": device.get("size"),
        "fstype": device.get("fstype"),
        "pttype": device.get("pttype"),
        "ptuuid": device.get("ptuuid"),
        "log-sec": device.get("log-sec"),
        "partuuid": device.get("partuuid"),
        "parttype": device.get("parttype"),
        "uuid": device.get("uuid"),
        "start": device.get("start"),
        "ro": _flag(device.get("ro")),
        "mountpoints": sorted(str(p) for p in (device.get("mountpoints") or []) if p),
        "children": children,
    }


def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


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
    fingerprint = _digest(descriptor)
    layout_fingerprint = _digest(_layout(disks[index]))
    return {
        "operation": "read_only_target_plan",
        "selected_identity": selected_identity,
        "current_device_path_unstable": selected["path"],
        "hardware_fingerprint": fingerprint,
        "layout_fingerprint": layout_fingerprint,
        "target": selected,
        "non_target_disks": [inspect_disk(d) for i, d in enumerate(disks) if i != index],
        "requires_revalidation_before_write": True,
        "requires_backup": True,
        "requires_destructive_confirmation": True,
        "install_ready": False,
        "write_operations_available": False,
        "warning": "Read-only plan is NOT permission to erase or install anything",
    }


def revalidate_target(payload: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    """Compare a previously reviewed plan against a fresh lsblk snapshot.

    This is an advisory check, not an atomic device lock or authorization.
    The eventual writer must enforce its own exclusive device binding.
    """
    if previous.get("operation") != "read_only_target_plan":
        raise TargetSelectionError("Expected a previously reviewed read-only plan")
    selected = previous.get("selected_identity")
    current = read_only_target_plan(payload, selected)
    for key in ("hardware_fingerprint", "layout_fingerprint"):
        if not previous.get(key) or previous[key] != current[key]:
            raise TargetSelectionError(f"Target changed since review: {key}")
    return current
