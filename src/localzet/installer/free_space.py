"""GPT free-space planning for a future installer backend. No writes.

Only accepts independent lsblk and sfdisk JSON observations. No resizing,
formatting, mounting, partition writes or bootloader commands are generated.
A plan is not authorization, a device lock or proof of filesystem health.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import uuid

from localzet.installer.target import identity, read_only_target_plan, _digest
from localzet.installer.preflight import MIN_SIZE_BYTES, _flag

EFI_TYPE = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"
MIB = 1024**2


def _integer(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f"Invalid {name}")
    return value


def _guid(value, name):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise ValueError(f"Missing or invalid {name}") from None


def inspect_free_space(payload: dict, selected: str, live_disk: str | None,
                       table_payload: dict, *, source_known: bool) -> dict:
    if not source_known:
        raise ValueError("Boot medium is not identified")
    target = read_only_target_plan(payload, selected)
    disks = [d for d in payload["blockdevices"] if d.get("type") == "disk"]
    disk = next(d for d in disks if identity(d) == selected)
    path = disk["path"]
    if path == live_disk:
        raise ValueError("Boot medium cannot be a target")
    if disk.get("tran") not in ("nvme", "sata", "ata"):
        raise ValueError("Only internal NVMe/SATA SSDs are reviewed")
    if str(disk.get("pttype") or "").lower() != "gpt" or disk.get("fstype"):
        raise ValueError("Only existing GPT disks with no whole-disk filesystem are reviewed")
    table = table_payload.get("partitiontable")
    if not isinstance(table, dict) or table.get("label") != "gpt":
        raise ValueError("GPT partition table required")
    if table.get("device") != path or table.get("unit") != "sectors":
        raise ValueError("Partition table does not match target or uses unknown units")
    sector = _integer(table.get("sectorsize"), "sector size")
    if sector not in (512, 4096):
        raise ValueError("Unsupported logical sector size")
    capacity = _integer(disk.get("size"), "disk size")
    if capacity % sector:
        raise ValueError("Disk size is not sector aligned")
    first = _integer(table.get("firstlba"), "first usable LBA")
    last = _integer(table.get("lastlba"), "last usable LBA")
    if not 2 <= first <= last < capacity // sector - 1:
        raise ValueError("Invalid usable GPT bounds")
    table_id = _guid(table.get("id"), "GPT disk UUID")
    rows = table.get("partitions")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Existing partitions required; use dedicated SSD planner otherwise")
    children = disk.get("children") or []
    if len(rows) != len(children) or any(
            c.get("type") != "part" or c.get("children") or _flag(c.get("ro")) is not False
            for c in children):
        raise ValueError("Partition inventory mismatch or nested/read-only partition")
    by_path = {c.get("path"): c for c in children}
    if len(by_path) != len(children) or None in by_path:
        raise ValueError("Ambiguous partition paths")
    seen_paths, seen_ids = set(), set()
    partitions = []
    for row in rows:
        node = row.get("node")
        if node in seen_paths or node not in by_path:
            raise ValueError("Partition device mismatch")
        seen_paths.add(node)
        child = by_path[node]
        start = _integer(row.get("start"), "partition start")
        size = _integer(row.get("size"), "partition size")
        part_id = _guid(row.get("uuid"), "partition UUID")
        kind = _guid(row.get("type"), "partition type")
        if (not size or start < first or start + size - 1 > last
                or part_id in seen_ids
                or part_id != _guid(child.get("partuuid"), "lsblk partition UUID")
                or kind != _guid(child.get("parttype"), "lsblk partition type")
                or size * sector != _integer(child.get("size"), "lsblk partition size")):
            raise ValueError("Partition bounds, identity or size mismatch")
        seen_ids.add(part_id)
        partitions.append({"path": node, "start_lba": start, "end_lba_exclusive": start + size,
                           "partuuid": part_id, "type": kind, "filesystem": child.get("fstype")})
    partitions.sort(key=lambda p: p["start_lba"])
    cursor = first
    free = []
    align = MIB // sector

    def gap(start, end):
        # Half-open intervals; round inward so no existing sector is consumed.
        lo = (start + align - 1) // align * align
        hi = end // align * align
        if hi > lo:
            free.append({"start_lba": lo, "end_lba_exclusive": hi,
                         "size_bytes": (hi - lo) * sector,
                         "meets_root_minimum": (hi - lo) * sector >= MIN_SIZE_BYTES})

    for part in partitions:
        if part["start_lba"] < cursor:
            raise ValueError("Overlapping GPT partitions")
        gap(cursor, part["start_lba"])
        cursor = part["end_lba_exclusive"]
    gap(cursor, last + 1)
    esps = [p for p in partitions if p["type"] == EFI_TYPE]
    # Fingerprint covers the exact sector map, not just rounded free space.
    layout = {"disk_uuid": table_id, "sector_size": sector, "first_lba": first,
              "last_lba": last, "partitions": partitions}
    return {
        "operation": "read_only_gpt_free_space",
        "selected_identity": selected,
        "path": path,
        "hardware_fingerprint": target["hardware_fingerprint"],
        "layout_fingerprint": target["layout_fingerprint"],
        "gpt_fingerprint": _digest(layout),
        "sector_size": sector,
        "partitions_to_preserve": partitions,
        "efi_partitions_to_preserve": esps,
        "aligned_free_extents": free,
        "bootloader_policy": "no ESP formatting or foreign loader overwrite; explicit EFI plan required",
        "requires_explicit_extent_selection": True,
        "requires_revalidation_before_write": True,
        "install_ready": False,
        "write_operations_available": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lsblk-json", type=Path, required=True)
    parser.add_argument("--sfdisk-json", type=Path, required=True)
    parser.add_argument("--identity", required=True)
    boot = parser.add_mutually_exclusive_group(required=True)
    boot.add_argument("--live-disk")
    boot.add_argument("--optical-boot", action="store_true")
    args = parser.parse_args()
    try:
        result = inspect_free_space(json.loads(args.lsblk_json.read_text()),
                                    args.identity, args.live_disk,
                                    json.loads(args.sfdisk_json.read_text()),
                                    source_known=True)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        parser.exit(2, f"Read-only plan rejected: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
