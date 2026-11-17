#!/usr/bin/env python3
"""Derive an About-only logo without altering the canonical artwork."""
import argparse
from pathlib import Path

BACKGROUND = b'<rect class="fil0" x="-7.59" y="7.62" width="19999.96" height="19999.96"/>'


def transparent_logo(source: bytes) -> bytes:
    if source.count(BACKGROUND) != 1:
        raise ValueError("Unexpected canonical logo background")
    return source.replace(BACKGROUND, b"", 1)


def dark_logo(source: bytes) -> bytes:
    result = transparent_logo(source)
    for old, new in (
        (b".fil1 {fill:black}", b".fil1 {fill:#F2EFF8}"),
        (b".fil2 {fill:black;fill-rule:nonzero}", b".fil2 {fill:#F2EFF8;fill-rule:nonzero}"),
    ):
        if result.count(old) != 1:
            raise ValueError("Unexpected canonical logo fill")
        result = result.replace(old, new, 1)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--dark", action="store_true")
    args = parser.parse_args()
    derive = dark_logo if args.dark else transparent_logo
    args.output.write_bytes(derive(args.source.read_bytes()))
