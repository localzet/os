#!/usr/bin/env python3
"""Conservative screenshot evidence checks for disposable QEMU guests."""
from pathlib import Path


def visual_metrics(path: Path, region=None):
    from PIL import Image, ImageStat
    with Image.open(path) as original:
        image = original.convert("RGB")
    if region:
        x, y, w, h = region
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(image.width, x+w), min(image.height, y+h)
        if x2-x1 < 300 or y2-y1 < 200:
            raise ValueError("Evidence region outside display")
        image = image.crop((x1, y1, x2, y2))
    image = image.resize((320, 200))
    gray = image.convert("L")
    colors = image.quantize(colors=32).getcolors()
    dominance = max(count for count, _ in colors) / (320*200)
    detailed_tiles = sum(
        ImageStat.Stat(gray.crop((x,y,x+40,y+25))).stddev[0] > 7
        for y in range(0,200,25) for x in range(0,320,40)
    )
    return {"dominance": round(dominance, 4), "detailed_tiles": detailed_tiles,
            "colors": len(colors)}


def meaningful(metrics):
    # Reject a powered-off display, blank white application or isolated text
    # on a flat frame. Not a substitute for human visual acceptance.
    return metrics["dominance"] < .97 and metrics["detailed_tiles"] >= 6 and metrics["colors"] >= 12


def document_ink(path: Path):
    """Count the original fixture's blue heading ink, away from editor chrome."""
    from PIL import Image
    with Image.open(path) as original:
        image = original.convert("RGB")
    w, h = image.size
    page = image.crop((w//8, h//3, w*7//8, h*4//5))
    return sum(20 <= r <= 65 and 65 <= g <= 125 and 130 <= b <= 205
               and b > g+35 and g > r+25 for r,g,b in page.getdata())
