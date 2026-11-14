#!/usr/bin/env python3
"""Apply only the reviewed distributor logo change to Ubuntu's patched source."""
import argparse
from pathlib import Path

LOGO = "/usr/share/localzet/brand/localzet.svg"
REPLACEMENTS = {
    "distributor_logo = get_option('distributor_logo')": f"distributor_logo = '{LOGO}'",
    "dark_mode_distributor_logo = get_option('dark_mode_distributor_logo')": f"dark_mode_distributor_logo = '{LOGO}'",
}


def patch(source: str) -> str:
    # Fail closed on upstream changes, rather than guessing new semantics.
    for old, new in REPLACEMENTS.items():
        if source.count(old) != 1:
            raise ValueError(f"Expected exactly one reviewed upstream line: {old}")
        source = source.replace(old, new)
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("meson_build", type=Path)
    args = parser.parse_args()
    original = args.meson_build.read_text()
    args.meson_build.write_text(patch(original))


if __name__ == "__main__":
    main()
