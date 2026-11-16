#!/usr/bin/env python3
"""Generate the Executive dusk colorway from the licensed signed-archive photo.

No network, generated scenery or external image sources. The derivative is
CC BY-SA 4.0; see assets/wallpapers/ATTRIBUTION.txt.
"""
import argparse
from pathlib import Path
import os
import tempfile


def render(source, output):
    from PIL import Image, ImageOps, ImageEnhance, ImageFilter
    with Image.open(source) as original:
        if original.width < 1920 or original.height < 1080:
            raise ValueError("Wallpaper source resolution below Full HD")
        image = ImageOps.fit(ImageOps.exif_transpose(original).convert("RGB"),
                             (3840, 2160), method=Image.Resampling.LANCZOS)
    # Preserve mountain/lake detail and moderate saturation. A dusk grade
    # rather than an artificial new sky or an opaque dark rectangle.
    image = ImageEnhance.Color(image).enhance(.82)
    curves = []
    for floor, ceiling, exponent in ((8, 202, 1.20), (15, 185, 1.12), (30, 214, 1.02)):
        curves.extend(round(floor + (ceiling - floor) * (v / 255) ** exponent)
                      for v in range(256))
    image = image.point(curves)
    # Subtle dark edges and warm light near the right-hand horizon.
    width, height = 480, 270
    light, shadow = Image.new("L", (width, height)), Image.new("L", (width, height))
    light.putdata([round(42 * max(0, 1 - ((x/width - .76)/.62)**2
                                      - ((y/height - .31)/.36)**2)**2)
                   for y in range(height) for x in range(width)])
    shadow.putdata([round(min(75, 13 + 32 * ((x/width-.5)*2)**2 +
                                      24 * ((y/height-.45)*2)**2))
                    for y in range(height) for x in range(width)])
    image = Image.composite(Image.new("RGB", image.size, "#b76c64"), image,
                            light.resize(image.size, Image.Resampling.BICUBIC))
    image = Image.composite(Image.new("RGB", image.size, "#091321"), image,
                            shadow.resize(image.size, Image.Resampling.BICUBIC))
    # Preblur in image space, with sufficient radius at 4K. The derivative
    # is tinted here, not by translucent CSS over an unblurred desktop.
    glass = image.resize((960, 540), Image.Resampling.LANCZOS).filter(
        ImageFilter.GaussianBlur(14)).resize(image.size, Image.Resampling.BICUBIC)
    glass = Image.blend(glass, Image.new("RGB", image.size, "#101b2d"), .72)
    output = Path(output)
    save_jpeg(image, output)
    save_jpeg(glass, output.with_name(output.stem + "-glass.jpg"))


def save_jpeg(image, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".executive-", suffix=".jpg", dir=output.parent)
    os.close(fd)
    try:
        image.save(temp, format="JPEG", quality=94, subsampling=0, optimize=True)
        os.chmod(temp, 0o644)
        os.replace(temp, output)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    render(args.source, args.output)
