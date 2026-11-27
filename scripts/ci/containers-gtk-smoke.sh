#!/usr/bin/env bash
set -Eeuo pipefail
export PYTHONPATH="$PWD/src" GDK_BACKEND=x11 GSK_RENDERER=cairo GTK_A11Y=none
export OUT="$PWD/out/containers-gtk"
mkdir -p "$OUT"
# Do not install/start an engine to make this test pass.
xvfb-run -a -s '-screen 0 1440x900x24' dbus-run-session -- bash -s <<'GTK_TEST'
set -Eeuo pipefail
gsettings set org.gnome.desktop.interface color-scheme prefer-dark
gsettings set org.gnome.desktop.a11y.interface high-contrast false
python3 -m localzet.containers_app > "$OUT/app.log" 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true' EXIT
window=""
for attempt in $(seq 1 30); do
    kill -0 "$pid" || { cat "$OUT/app.log"; exit 1; }
    window="$(xdotool search --onlyvisible --name 'Localzet Containers' | head -n1 || true)"
    [[ -n "$window" ]] && break
    sleep 1
done
test -n "$window"
sleep 3
import -window "$window" "$OUT/window.png"
# Exercise actual persistent navigation, even with no Docker daemon.
for page in 2 3 4 5 1; do
    xdotool windowfocus "$window" key "ctrl+$page"
    sleep 2
    case "$page" in
        1) title="Контейнеры";;
        2) title="Compose";;
        3) title="Образы";;
        4) title="Тома";;
        5) title="Сети";;
    esac
    xdotool getwindowname "$window" | grep -F "$title"
    import -window "$window" "$OUT/page-$page.png"
    kill -0 "$pid"
done
gsettings set org.gnome.desktop.interface color-scheme prefer-light
sleep 2
import -window "$window" "$OUT/window-light.png"
gsettings set org.gnome.desktop.interface color-scheme prefer-dark
gsettings set org.gnome.desktop.a11y.interface high-contrast true
sleep 2
import -window "$window" "$OUT/window-contrast.png"
kill -0 "$pid"
! grep -q 'Traceback (most recent call last)' "$OUT/app.log"
kill "$pid" 2>/dev/null || true
wait "$pid" 2>/dev/null || true
trap - EXIT
python3 "$PWD/scripts/ci/appearance-runtime-smoke.py"
python3 - "$OUT" <<'PALETTE'
from collections import Counter
from pathlib import Path
import sys
from PIL import Image, ImageChops, ImageStat

root = Path(sys.argv[1])
dark = Image.open(root / "window.png").convert("RGB")
light = Image.open(root / "window-light.png").convert("RGB")
contrast = Image.open(root / "window-contrast.png").convert("RGB")
assert dark.size == light.size == contrast.size
counts = Counter(dark.getdata())
required = {"#10091E": 10000, "#28183F": 5000, "#F4EEFF": 100}
for color, minimum in required.items():
    actual = counts[tuple(bytes.fromhex(color[1:]))]
    assert actual >= minimum, f"dark Aurora token {color}: {actual} < {minimum}"
difference = ImageStat.Stat(ImageChops.difference(dark, light)).mean
assert sum(difference) / 3 >= 5, f"explicit light preference did not change the app: {difference}"
light_counts = Counter(light.getdata())
for color in ("#10091E", "#28183F"):
    actual = light_counts[tuple(bytes.fromhex(color[1:]))]
    assert actual < 2000, f"dark token {color} leaked into light mode: {actual}"
print("PASS: Violet × Ember dark palette, explicit light mode, and high-contrast runtime")
PALETTE
GTK_TEST
