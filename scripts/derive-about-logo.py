#!/usr/bin/env python3
"""Derive an About-only logo without altering the canonical artwork."""
import sys
from pathlib import Path

BACKGROUND = b'<rect class="fil0" x="-7.59" y="7.62" width="19999.96" height="19999.96"/>'


def transparent_logo(source: bytes) -> bytes:
    if source.count(BACKGROUND) != 1:
        raise ValueError("Unexpected canonical logo background")
    return source.replace(BACKGROUND, b"", 1)


if __name__ == "__main__":
    Path(sys.argv[2]).write_bytes(transparent_logo(Path(sys.argv[1]).read_bytes()))
