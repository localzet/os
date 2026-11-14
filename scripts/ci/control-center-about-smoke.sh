#!/usr/bin/env bash
# Invoked only in isolated Xvfb session on disposable runner.
set -Eeuo pipefail
export GDK_BACKEND=x11 GTK_A11Y=none
export LC_ALL=C.UTF-8
gsettings set org.gnome.desktop.interface color-scheme prefer-dark
gnome-control-center about > "$OUT/about.log" 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true' EXIT
window=""
for i in $(seq 1 30); do
    kill -0 "$pid"
    window="$(xdotool search --onlyvisible --class 'gnome-control-center' 2>/dev/null | head -n 1 || true)"
    [[ -n "$window" ]] && break
    sleep 1
done
test -n "$window"
sleep 3
xdotool getwindowname "$window" > "$OUT/about-window.txt"
import -window "$window" "$OUT/about.png"
python3 - "$OUT/about.png" <<'PY'
from PIL import Image
import sys
im = Image.open(sys.argv[1]).convert("RGB")
assert im.width >= 400 and im.height >= 300
assert len(set(im.resize((80, 50)).getdata())) > 25
print("PASS: nonblank About window capture; inspect actual logo visually")
PY
