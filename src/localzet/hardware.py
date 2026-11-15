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
import os
import platform
import subprocess


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


PACKAGE = re.compile(r"[a-z0-9][a-z0-9+.-]{0,127}")
NVIDIA_DRIVER = re.compile(r"nvidia-driver-[0-9]{3}(?:-open)?")


def secure_boot(efi: Path = Path("/sys/firmware/efi")) -> str:
    if not efi.is_dir():
        return "not-uefi"
    try:
        # efivarfs stores four attribute bytes before the one-byte value.
        value = (efi / "efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c").read_bytes()
        if len(value) == 5 and value[4] in (0, 1):
            return "enabled" if value[4] else "disabled"
    except OSError:
        pass
    return "unknown"


def parse_recommended(output: str) -> tuple[tuple[str, ...], ...]:
    """Ubuntu 26.04 --recommended lists package and optional kernel module."""
    rows = []
    for line in output.splitlines():
        if not line.strip():
            continue
        tokens = tuple(line.split())
        if len(tokens) not in (1, 2) or not all(PACKAGE.fullmatch(token) for token in tokens):
            raise ValueError("Unrecognized ubuntu-drivers recommendation")
        if len(tokens) == 2 and not tokens[1].startswith("linux-modules-"):
            raise ValueError("Unrecognized kernel module recommendation")
        if tokens not in rows:
            rows.append(tokens)
    return tuple(rows)


def recommendations() -> dict:
    try:
        proc = subprocess.run(["/usr/bin/ubuntu-drivers", "list", "--recommended"],
            capture_output=True, text=True, check=True, timeout=45,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8", "HOME": str(Path.home())})
        rows = parse_recommended(proc.stdout)
        return {"status": "observed", "packages": [list(row) for row in rows],
                "privileged_inventory": os.geteuid() == 0}
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"status": "unavailable", "packages": [], "privileged_inventory": False}


def archive_candidate(cache, name: str) -> dict:
    if not re.fullmatch(r"[a-z0-9][a-z0-9+.-]{0,127}(?::[a-z0-9-]{1,16})?", name):
        raise ValueError("Invalid package name")
    try:
        candidate = cache[name].candidate
    except KeyError:
        candidate = None
    if candidate is None:
        return {"name": name, "status": "unavailable"}
    origins = [origin for origin in candidate.origins
               if not (origin.archive == "now" and origin.origin == "")]
    # Reject mixed origins and locally installed-only versions. Origin metadata
    # is a screening condition, not proof of an independently pinned key.
    trusted = bool(origins) and all(origin.trusted and origin.origin == "Ubuntu"
        and origin.archive in ("resolute", "resolute-updates", "resolute-security")
        for origin in origins)
    return {"name": name, "version": candidate.version,
            "status": "ubuntu-candidate" if trusted else "review-origin",
            "download_bytes": candidate.size, "installed_bytes": candidate.installed_size}


def resolve_local(devices: tuple[PCIDevice, ...]) -> dict:
    result = plan(devices)
    result["kernel"] = platform.release()
    result["secure_boot"] = secure_boot()
    suggested = recommendations()
    result["recommendations"] = suggested
    nvidia = result["nvidia_gpu_detected"]
    names = {name for row in suggested["packages"] for name in row}
    if nvidia:
        names.update(("cuda-toolkit", "cuda-toolkit-13-1", "nvidia-cuda-toolkit"))
    try:
        import apt
        cache = apt.Cache()
        result["archive_candidates"] = [archive_candidate(cache, name) for name in sorted(names)]
        result["archive_status"] = "observed"
    except (ImportError, OSError, RuntimeError, SystemError, ValueError):
        result["archive_candidates"] = []
        result["archive_status"] = "unavailable"
    result["nvidia_desktop_recommendations"] = [row for row in suggested["packages"]
        if nvidia and NVIDIA_DRIVER.fullmatch(row[0])]
    result["cuda_compatible"] = None
    result["install_ready"] = False
    return result


def nvidia_driver_targets(result: dict) -> tuple[str, ...]:
    """Choose only one recommended desktop series, with matching signed ABI."""
    if not result["nvidia_gpu_detected"]:
        return ()
    rows = result["nvidia_desktop_recommendations"]
    if result["recommendations"]["status"] != "observed" or len(rows) != 1:
        raise ValueError("A unique NVIDIA desktop recommendation is required")
    driver = rows[0][0]
    if not NVIDIA_DRIVER.fullmatch(driver):
        raise ValueError("Invalid NVIDIA driver recommendation")
    kernel = result["kernel"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-[0-9]+-generic", kernel):
        raise ValueError("Only the running Ubuntu generic kernel is supported")
    if result["secure_boot"] not in ("enabled", "disabled", "not-uefi"):
        raise ValueError("Secure Boot state unknown")
    suffix = driver.removeprefix("nvidia-driver-")
    # Include the flavour metapackage for future kernel updates and the exact
    # running ABI for the next boot. No DKMS fallback or server series.
    return ("linux-modules-nvidia-" + suffix + "-generic",
            "linux-modules-nvidia-" + suffix + "-" + kernel, driver)


def simulate_packages(cache, targets: tuple[str, ...], *, retain_marks: bool = False) -> dict:
    """Resolve APT in memory; retain reviewed marks only for an authorized caller."""
    import shutil
    if not targets or len(set(targets)) != len(targets) or not all(
            isinstance(name, str) and PACKAGE.fullmatch(name) for name in targets):
        raise ValueError("Invalid transaction targets")
    if cache.broken_count or getattr(cache, "dpkg_journal_dirty", False):
        raise ValueError("APT or dpkg requires recovery before driver setup")
    changes = []
    validated = False
    try:
        for name in targets:
            if archive_candidate(cache, name)["status"] != "ubuntu-candidate":
                raise ValueError("No reviewed Ubuntu candidate: " + name)
            cache[name].mark_install(auto_fix=True, auto_inst=True, from_user=True)
        if cache.broken_count:
            raise ValueError("Unresolved dependency transaction")
        for name in targets:
            package = cache[name]
            if package.marked_delete or not (package.marked_install or package.marked_upgrade
                    or (package.installed and package.installed.version == package.candidate.version)):
                raise ValueError("Requested package not resolved: " + name)
        for package in cache.get_changes():
            name = package.name
            if package.marked_delete or package.marked_downgrade:
                raise ValueError("Removal or downgrade requires separate review: " + name)
            if name.startswith("nvidia-dkms-") or name == "dkms":
                raise ValueError("DKMS requires a separate signing/MOK workflow")
            if not (package.marked_install or package.marked_upgrade):
                raise ValueError("Unsupported package change: " + name)
            candidate = archive_candidate(cache, name)
            if candidate["status"] != "ubuntu-candidate":
                raise ValueError("Unreviewed dependency origin: " + name)
            changes.append({"name": name, "version": candidate["version"],
                            "action": "upgrade" if package.is_installed else "install"})
        download = max(0, cache.required_download)
        installed = max(0, cache.required_space)
        # Conservative screening, not a reservation or per-mount calculation.
        free = min(shutil.disk_usage(path).free for path in ("/", "/var/cache/apt/archives", "/boot"))
        enough = free >= download + installed + 512 * 1024 * 1024
        validated = enough
        return {"status": "simulated" if enough else "insufficient-space",
                "targets": list(targets), "changes": sorted(changes, key=lambda row: row["name"]),
                "download_bytes": download, "additional_installed_bytes": installed,
                "minimum_free_bytes": free, "install_ready": False}
    finally:
        if not (retain_marks and validated):
            cache.clear()


def simulate_driver_setup(devices: tuple[PCIDevice, ...]) -> dict:
    result = resolve_local(devices)
    try:
        targets = nvidia_driver_targets(result)
        if not targets:
            result["transaction"] = {"status": "not-applicable", "install_ready": False}
        else:
            import apt
            result["transaction"] = simulate_packages(apt.Cache(), targets)
    except (ImportError, OSError, RuntimeError, SystemError, ValueError) as error:
        result["transaction"] = {"status": "blocked", "reason": str(error), "install_ready": False}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolve", action="store_true", help="Inspect local Ubuntu recommendations and APT cache without network access")
    parser.add_argument("--simulate", action="store_true", help="Simulate a recommended NVIDIA driver transaction; never install")
    parser.add_argument("--cuda", action="store_true", help="Inspect compatible CUDA toolkit and simulate its installation")
    args = parser.parse_args()
    try:
        devices = inventory()
    except OSError as error:
        parser.exit(1, f"Hardware inventory unavailable: {error}\n")
    result = simulate_driver_setup(devices) if args.simulate else resolve_local(devices) if args.resolve else plan(devices)
    if args.cuda:
        from localzet.hardware_cuda import inspect_cuda
        result["cuda"] = inspect_cuda(devices)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
