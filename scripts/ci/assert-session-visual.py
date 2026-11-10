#!/usr/bin/env python3
"""Check whether a QEMU screenshot plausibly shows the Localzet wallpaper.

This is a P1 visual regression *heuristic*, not proof of GNOME login or a
general desktop classifier. The reference Localzet wallpaper has large
saturated blue/purple areas absent from the monochrome GDM greeter.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def saturated_share(pixels: list[tuple[int, int, int]], contrast: int = 35) -> float:
    if not pixels:
        return 0.0
    return sum(max(rgb) - min(rgb) > contrast for rgb in pixels) / len(pixels)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    from PIL import Image

    im = Image.open(args.image).convert("RGB")
    if im.width < 640 or im.height < 400:
        raise SystemExit("Framebuffer is too small to assess.")
    samples = list(im.resize((160, 100)).getdata())
    share = saturated_share(samples)
    passed = share >= 0.12
    report = {
        "width": im.width,
        "height": im.height,
        "saturated_share": round(share, 4),
        "reference": "Localzet OS P1 wallpaper",
        "heuristic_pass": passed,
        "note": "Does not by itself prove a functioning desktop session.",
    }
    print(json.dumps(report, ensure_ascii=False))
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
