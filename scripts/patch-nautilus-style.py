#!/usr/bin/env python3
"""Append only a reviewed application-local CSS overlay to Nautilus 50."""
import argparse
from pathlib import Path

MARKER = "/* Localzet Executive:"
REQUIRED = (".nautilus-pathbar", ".nautilus-grid-view gridview",
            ".nautilus-list-view columnview", ".floating-bar")


def patch(source: str, overlay: str) -> str:
    if MARKER in source:
        raise ValueError("Executive overlay already present")
    if not all(selector in source for selector in REQUIRED):
        raise ValueError("Nautilus stylesheet changed; review current source")
    if not overlay.startswith(MARKER) or "@media (prefers-color-scheme: dark) and (prefers-contrast: no-preference)" not in overlay:
        raise ValueError("Expected reviewed dark-only, normal-contrast overlay")
    return source.rstrip() + "\n\n" + overlay.rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("overlay", type=Path)
    args = parser.parse_args()
    args.source.write_text(patch(args.source.read_text(), args.overlay.read_text()))


if __name__ == "__main__":
    main()
