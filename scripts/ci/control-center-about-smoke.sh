#!/usr/bin/env bash
# Invoked only in isolated Xvfb session on disposable runner.
set -Eeuo pipefail
export GDK_BACKEND=x11 GTK_A11Y=none XDG_CURRENT_DESKTOP=GNOME
export LC_ALL=C.UTF-8
gsettings set org.gnome.desktop.interface color-scheme prefer-dark
gnome-control-center system about > "$OUT/about.log" 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true' EXIT
# A mapped X11 window need not have rendered its first frame yet.
# Retain the original size and color-diversity requirements.
for i in $(seq 1 30); do
    kill -0 "$pid" || { cat "$OUT/about.log"; exit 1; }
    while IFS= read -r window; do
        [[ -n "$window" ]] || continue
        xdotool getwindowname "$window" > "$OUT/about-window.txt" || continue
        import -window "$window" "$OUT/about.png" || continue
        if python3 - "$OUT/about.png" <<'PY'
from PIL import Image
import sys
im = Image.open(sys.argv[1]).convert("RGB")
colors = len(set(im.resize((80, 50)).getdata()))
print(f"About capture: {im.width}x{im.height}, {colors} sampled colors")
sys.exit(not (im.width >= 400 and im.height >= 300 and colors > 25))
PY
        then
            echo "PASS: nonblank About window capture; inspect actual logo visually"
            exit 0
        fi
    done < <(xdotool search --onlyvisible --class 'gnome-control-center' 2>/dev/null || true)
    sleep 1
done
cat "$OUT/about.log"
echo "FAIL: About window did not render a qualifying frame" >&2
exit 1
