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


def patch_about(source: str) -> str:
    # Clamp is vertical, but an unshrinkable SVG keeps its intrinsic size.
    # Preserve the original artwork while limiting its presentation.
    old = """          maximum-size: 192;
          tightening-threshold: 192;

          child: Picture os_logo {
            can-shrink: false;"""
    new = """          maximum-size: 144;
          tightening-threshold: 144;

          child: Picture os_logo {
            height-request: 144;
            can-shrink: true;"""
    if source.count(old) != 1:
        raise ValueError("Unexpected upstream About logo layout")
    return source.replace(old, new)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("meson_build", type=Path)
    parser.add_argument("--about-blueprint", type=Path, required=True)
    args = parser.parse_args()
    original = args.meson_build.read_text()
    brand = patch(original)
    about = patch_about(args.about_blueprint.read_text())
    args.meson_build.write_text(brand)
    args.about_blueprint.write_text(about)


if __name__ == "__main__":
    main()
