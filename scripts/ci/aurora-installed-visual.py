#!/usr/bin/env python3
"""Verify the installed ISO's real GNOME desktop and lock-screen screenshots.

This consumes QEMU screenshots from the installed image. It never substitutes
a devkit, generated mockup, or the absent owner reference PNG.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from PIL import Image, ImageStat


def purple_ratio(image: Image.Image, box: tuple[int, int, int, int]) -> float:
    crop = image.crop(box).convert("RGB")
    pixels = crop.getdata()
    total = crop.width * crop.height
    purple = sum(
        1 for red, green, blue in pixels
        if blue > red * 1.10 and red > green * 1.10 and blue > 70
    )
    return purple / max(1, total)


def textured_tiles(image: Image.Image, box: tuple[int, int, int, int], tile: int = 16) -> int:
    crop = image.crop(box).convert("RGB")
    count = 0
    for top in range(0, crop.height - tile + 1, tile):
        for left in range(0, crop.width - tile + 1, tile):
            stats = ImageStat.Stat(crop.crop((left, top, left + tile, top + tile)))
            if max(stats.stddev) > 10:
                count += 1
    return count


def analyze_desktop(path: Path, tokens: dict) -> dict:
    image = Image.open(path).convert("RGB")
    width, height = image.size
    if width < 1024 or height < 640:
        raise AssertionError(f"Installed desktop resolution too small: {image.size}")

    density = tokens["density"]
    panel_height = max(24, min(48, round(density["panelHeight"] * 1.25)))
    dock_height = max(56, min(96, round(density["dockHeight"] * 1.5)))
    panel = (0, 0, width, panel_height)
    dock_half_width = round(width * 0.15)
    dock = (width // 2 - dock_half_width, height - dock_height,
            width // 2 + dock_half_width, height - 4)
    wallpaper = (0, panel_height, width, height - dock_height)

    panel_purple = purple_ratio(image, panel)
    dock_purple = purple_ratio(image, dock)
    wallpaper_tiles = textured_tiles(image, wallpaper)
    wallpaper_colors = len(set(image.crop(wallpaper).getdata()))

    if panel_purple < 0.65:
        raise AssertionError(f"Installed GNOME panel is not Violet × Ember: {panel_purple:.3f}")
    if dock_purple < 0.04:
        raise AssertionError(f"Installed GNOME dock lacks its restrained glass/violet surface: {dock_purple:.3f}")
    if wallpaper_tiles < 100 or wallpaper_colors < 1000:
        raise AssertionError(
            f"Installed wallpaper is blank/flat: tiles={wallpaper_tiles}, colors={wallpaper_colors}"
        )

    return {
        "size": [width, height],
        "panel_purple_ratio": round(panel_purple, 4),
        "dock_purple_ratio": round(dock_purple, 4),
        "wallpaper_textured_tiles": wallpaper_tiles,
        "wallpaper_unique_colors": wallpaper_colors,
        "panel_height_token": density["panelHeight"],
        "dock_height_token": density["dockHeight"],
    }


def analyze_lock(path: Path) -> dict:
    image = Image.open(path).convert("RGB")
    width, height = image.size
    if width < 1024 or height < 640:
        raise AssertionError(f"Installed lock screen resolution too small: {image.size}")
    colors = len(set(image.getdata()))
    tiles = textured_tiles(image, (0, 0, width, height))
    mean = ImageStat.Stat(image).mean
    if colors < 1000 or tiles < 64 or sum(mean) / 3 > 180:
        raise AssertionError(
            f"Installed lock screen is blank or not Aurora: colors={colors}, tiles={tiles}, mean={mean}"
        )
    return {
        "size": [width, height],
        "unique_colors": colors,
        "textured_tiles": tiles,
        "mean_rgb": [round(value, 2) for value in mean],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--desktop", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--tokens", type=Path, default=Path("assets/design-tokens.json"))
    parser.add_argument("--output", type=Path, default=Path("out/aurora-installed-visual.json"))
    args = parser.parse_args()

    tokens = json.loads(args.tokens.read_text())
    if tokens["name"] != "Localzet Aurora — Professional":
        raise AssertionError("Unexpected design token set")
    if tokens["colors"]["primary"].upper() != "#9B72F2":
        raise AssertionError("Aurora primary violet changed without visual review")
    if tokens["colors"]["accent"].upper() != "#FF7E00":
        raise AssertionError("Aurora ember accent changed without visual review")

    result = {
        "source": "installed-iso-qemu-screenshots",
        "desktop": analyze_desktop(args.desktop, tokens),
        "lock": analyze_lock(args.lock),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    print("PASS: actual installed Aurora Professional desktop and lock screenshots", flush=True)


if __name__ == "__main__":
    main()
