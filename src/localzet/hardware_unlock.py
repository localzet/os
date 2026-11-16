"""Read-only GPU Unlocker compatibility inventory; never install or activate."""
from pathlib import Path

UPSTREAM = "https://github.com/Zagitta/gpu-unlock"
REFERENCE = "7eb51bccae0a0b7e599e084d971170e9a1e82d0c"
# Exact device IDs from the pinned upstream compatibility table.
FAMILIES = {
    "turing": frozenset("1e03 1e04 1e07 1e2d 1e2e 1e81 1e82 1e84 1e87 1e89 1ec2 1ec7 1f02 1f03 1f06 1f07 1f08 1f42 1f47".split()),
    "ada": frozenset("2684 2685 2689 2702 2704 2705 2709 2757 2782 2783 2786 2803 2805 2882 28a0 28e0 28e1".split()),
    "ampere": frozenset("2200 2203 2204 2205 2206 2207 2208 220a 220d 2216 222b 222f 2414 2480 2482 2483 2484 2486 2487 2488 2489 248a 248c 248d 248e 249c 249d 249f 24a0 24a4 24ac 24ad 24af 24bf 24c0 24c7 24c8 24c9 24dc 24dd 24df 24e0 2501 2503 2504 2505 2507 2508 2509 252f 2544".split()),
}


def assess(devices, module_root=Path("/sys/module")):
    rows = []
    for device in devices:
        if device.vendor != "10de" or not device.device_class.startswith("03"):
            continue
        family = next((family for family, ids in FAMILIES.items()
                       if device.device in ids), None)
        status = ("upstream-candidate" if family == "ampere" else
                  "experimental" if family else "unsupported")
        rows.append({"address": device.address, "device": device.device,
                     "family": family, "status": status})
    return {"schema": 1, "mode": "read-only", "upstream": UPSTREAM,
            "reference": REFERENCE, "devices": rows,
            "module_present": (module_root / "gpu_unlock").is_dir(),
            "activation_available": False, "speedup_verified": False}


def review_status(assessment, boot_state):
    """User-facing readiness only; a PCI match never authorizes activation."""
    devices = assessment["devices"]
    if not devices:
        compatibility = "no-gpu"
    elif all(row["status"] == "unsupported" for row in devices):
        compatibility = "unsupported"
    elif any(row["status"] == "unsupported" for row in devices):
        compatibility = "mixed"
    elif any(row["status"] == "experimental" for row in devices):
        compatibility = "experimental"
    else:
        compatibility = "candidate"
    return {"compatibility": compatibility,
            "secure_boot": boot_state if boot_state in ("enabled", "disabled", "not-uefi") else "unknown",
            "module_present": assessment["module_present"],
            "activation_available": False,
            "blocker": "release-review-required",
            "speedup_verified": False}
