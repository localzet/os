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



def wallpaper_similarity(reference_path: Path, candidate_path: Path) -> float:
    """Compare the expected GNOME 50 lock blur with the installed lock capture.

    GNOME Shell 50's unlockDialog.js applies BLUR_RADIUS=90 and
    BLUR_BRIGHTNESS=0.65 to a BackgroundManager sourced from
    org.gnome.desktop.background. The reference is therefore transformed by
    the real compositor constants before comparison; the observed lock image
    receives only a small denoise pass. This avoids treating the intentional
    90px blur as a missing wallpaper while still rejecting the default flat
    gradient. Clock/date and dock regions are excluded.
    """
    from PIL import Image, ImageEnhance, ImageFilter

    with Image.open(reference_path) as source:
        reference = source.convert("RGB")
    with Image.open(candidate_path) as source:
        candidate = source.convert("RGB")
    if reference.size != candidate.size or reference.width < 640 or reference.height < 400:
        raise ValueError("Desktop and lock captures must have the same usable display size")

    # The installed-image QEMU capture is 1280x800 at scale factor 1.
    # Preserve the physical blur radius if the capture resolution changes.
    scale = reference.height / 800.0
    expected = reference.filter(ImageFilter.GaussianBlur(radius=90 * scale))
    expected = ImageEnhance.Brightness(expected).enhance(0.65)
    observed = candidate.filter(ImageFilter.GaussianBlur(radius=max(2, 5 * scale)))
    size = (64, 40)
    a = expected.resize(size, Image.Resampling.LANCZOS).convert("L")
    b = observed.resize(size, Image.Resampling.LANCZOS).convert("L")

    # Central differences, aligned to 38x62 for both derivative directions.
    ax = [[(a.getpixel((x+1, y)) - a.getpixel((x-1, y))) / 2
           for x in range(1, 63)] for y in range(40)]
    bx = [[(b.getpixel((x+1, y)) - b.getpixel((x-1, y))) / 2
           for x in range(1, 63)] for y in range(40)]
    ay = [[(a.getpixel((x, y+1)) - a.getpixel((x, y-1))) / 2
           for x in range(64)] for y in range(1, 39)]
    by = [[(b.getpixel((x, y+1)) - b.getpixel((x, y-1))) / 2
           for x in range(64)] for y in range(1, 39)]
    mask = [[not (y < 1 or (10 <= y < 24 and 17 <= x < 46)
                  or (31 <= y < 37 and 17 <= x < 46))
             for x in range(62)] for y in range(38)]
    correlations = []
    for left, right in ((ax[1:-1], bx[1:-1]),
                        ([row[1:-1] for row in ay], [row[1:-1] for row in by])):
        x_values = [left[y][x] for y in range(38) for x in range(62) if mask[y][x]]
        y_values = [right[y][x] for y in range(38) for x in range(62) if mask[y][x]]
        mean_x, mean_y = sum(x_values) / len(x_values), sum(y_values) / len(y_values)
        centered_x = [value - mean_x for value in x_values]
        centered_y = [value - mean_y for value in y_values]
        var_x = sum(value * value for value in centered_x)
        var_y = sum(value * value for value in centered_y)
        if var_x <= 1e-6 or var_y <= 1e-6:
            correlations.append(0.0)
        else:
            covariance = sum(x * y for x, y in zip(centered_x, centered_y))
            correlations.append(covariance / (var_x * var_y) ** 0.5)
    return sum(correlations) / len(correlations)
