"""Read-only storage diagnosis: distinguish invisible disks from policy blocks."""
from __future__ import annotations

import json
from pathlib import Path
from localzet.installer.preflight import read_lsblk, inspect_disk

EFI_TYPE = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"


def storage_controllers(root: Path = Path("/sys/bus/pci/devices")) -> list[dict]:
    result = []
    for device in sorted(root.glob("*")):
        try:
            cls = (device / "class").read_text().strip().lower()
            vendor = (device / "vendor").read_text().strip().lower()
            identifier = (device / "device").read_text().strip().lower()
            driver = (device / "driver").resolve(strict=True).name if (device / "driver").is_symlink() else None
        except OSError:
            continue
        if cls.startswith("0x01") or driver == "vmd":
            result.append({"pci": device.name, "class": cls, "vendor": vendor,
                           "device": identifier, "driver": driver,
                           "intel_raid_or_vmd": vendor == "0x8086" and
                           (cls.startswith("0x0104") or driver == "vmd")})
    return result


def report(payload: dict, live_disk: str | None, controllers: list[dict]) -> dict:
    from localzet.installer.interactive import eligible_plan
    from localzet.installer.target import identity
    rows = []
    for disk in payload["blockdevices"]:
        if disk.get("type") != "disk":
            continue
        item = inspect_disk(disk)
        # No serials, WWNs or UUIDs in the diagnostic report.
        row = {k: item[k] for k in ("path", "model", "size_bytes", "transport", "partitions", "blockers")}
        row["boot_medium"] = disk.get("path") == live_disk
        row["eligible"] = False
        row["efi_partitions"] = [child.get("path") for child in disk.get("children") or []
                                 if str(child.get("parttype") or "").lower() == EFI_TYPE]
        if row["boot_medium"]:
            row["reason"] = "Загрузочный носитель"
        elif not identity(disk):
            row["reason"] = "Нет стабильного WWN или серийного номера"
        else:
            try:
                eligible_plan(payload, identity(disk), live_disk)
                row["eligible"] = True
                row["reason"] = "Доступен для проверки"
            except ValueError as error:
                row["reason"] = str(error)
        rows.append(row)
    internal = [row for row in rows if not row["boot_medium"] and row["transport"] != "usb"]
    return {"disks": rows, "controllers": controllers,
            "internal_disks_visible": len(internal),
            "intel_rst_possible": any(c["intel_raid_or_vmd"] for c in controllers),
            "writes_performed": False}


def describe(data: dict) -> str:
    lines = []
    for row in data["disks"]:
        size = row["size_bytes"] / 1024**3
        lines.append(f'{row["path"]} · {row["model"] or "Disk"} · {size:.1f} GiB — {row["reason"]}')
        if row["efi_partitions"]:
            lines.append("  EFI: " + ", ".join(row["efi_partitions"]) +
                         " (существующая загрузка требует сохранения)")
    if not data["internal_disks_visible"]:
        lines.append("Ядро не обнаружило внутренних накопителей.")
        if data["intel_rst_possible"]:
            lines.append("Обнаружен Intel RAID/VMD. Не отключайте RST без подготовки Windows.")
    for controller in data["controllers"]:
        lines.append(f'PCI {controller["pci"]} · {controller["vendor"]}:{controller["device"]} · '
                     f'драйвер {controller["driver"] or "не привязан"}')
    return "\n".join(lines) or "Накопители и контроллеры не обнаружены."


def main() -> int:
    from localzet.installer.interactive import live_source_disk
    try:
        live = live_source_disk()
    except (OSError, ValueError):
        live = None
    print(json.dumps(report(read_lsblk(), live, storage_controllers()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
