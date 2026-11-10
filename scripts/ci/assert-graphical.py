#!/usr/bin/env python3
"""Check systemd graphical.target evidence in an ANSI-colored QEMU serial log.

This is deliberately narrow: finding the word "graphical.target" anywhere
(including the queued-start message) is not proof that the target was reached.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

ANSI_CSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
TARGET = re.compile(r"\bReached target\s+graphical\.target\b", re.IGNORECASE)


def reached_graphical(raw: bytes) -> bool:
    cleaned = ANSI_CSI.sub("", raw.decode("utf-8", errors="replace"))
    return any(TARGET.search(line) for line in cleaned.splitlines())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("serial", type=Path)
    args = parser.parse_args()
    try:
        evidence = reached_graphical(args.serial.read_bytes())
    except OSError as error:
        parser.exit(2, f"Cannot read serial log: {error}\n")
    if evidence:
        print("PASS: systemd reached graphical.target (serial evidence)")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
