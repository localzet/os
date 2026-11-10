#!/usr/bin/env python3
"""Check explicit systemd graphical-target evidence in a QEMU serial log.

Two supported proofs:
- Exact systemd 'Reached target graphical.target' status line.
- A complete Localzet boot-diagnostics block with graphical_target=active
  and gdm_state=active. The service writes this directly to the guest's
  serial port, so a status check is possible even if systemd console
  output is routed to the framebuffer instead.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

ANSI_CSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
TARGET = re.compile(r"\bReached target\s+graphical\.target\b", re.IGNORECASE)
START = "LOCALZET_BOOT_EVIDENCE_BEGIN"
END = "LOCALZET_BOOT_EVIDENCE_END"


def _serial_text(raw: bytes) -> str:
    return ANSI_CSI.sub("", raw.decode("utf-8", errors="replace"))


def reached_graphical(raw: bytes) -> bool:
    cleaned = _serial_text(raw)
    if any(TARGET.search(line) for line in cleaned.splitlines()):
        return True
    # Never infer success from an incomplete/truncated block.
    # Accept a fully delimited health report from the guest itself.
    for match in re.finditer(
        re.escape(START) + r"\s*(.*?)\s*" + re.escape(END),
        cleaned,
        flags=re.DOTALL,
    ):
        lines = {line.strip() for line in match.group(1).splitlines()}
        if "graphical_target=active" in lines and "gdm_state=active" in lines:
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("serial", type=Path)
    args = parser.parse_args()
    try:
        evidence = reached_graphical(args.serial.read_bytes())
    except OSError as error:
        parser.exit(2, f"Cannot read serial log: {error}\n")
    if evidence:
        print("PASS: graphical.target and GDM active (guest serial evidence)")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
