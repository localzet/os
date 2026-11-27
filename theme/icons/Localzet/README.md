# Localzet icon theme

`index.theme` declares eight scalable freedesktop contexts. Application tiles
use the shared 48 px Aurora grid; action and status symbols use a 24 px
monochrome grid. SVG scaling covers requested sizes from 16 through 256 px.
Unprovided names resolve through `Adwaita,hicolor`.

The theme currently supplies Localzet app tiles, common GNOME actions,
categories, devices, MIME types, places, emblems, and common status states. It
is a coherent base set, not a claim that every freedesktop icon name has a
custom drawing. Third-party applications keep their installed upstream icons.

Regenerate the static generic set with:

```sh
python3 scripts/generate-icon-theme.py
```
