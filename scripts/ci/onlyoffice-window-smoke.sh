#!/usr/bin/env bash
set -Eeuo pipefail
# No sign-in, no online service, no disabled Chromium sandbox.
"$OFFICE_APP" > "$OUT/office.log" 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true' EXIT
window=""
for attempt in $(seq 1 45); do
    window="$(xdotool search --onlyvisible --class '[Dd]esktop[Ee]ditors|[Oo][Nn][Ll][Yy][Oo][Ff][Ff][Ii][Cc][Ee]' 2>/dev/null | head -n1 || true)"
    if [[ -z "$window" ]]; then
        window="$(xdotool search --onlyvisible --name '[Oo][Nn][Ll][Yy][Oo][Ff][Ff][Ii][Cc][Ee]|Desktop Editors' 2>/dev/null | head -n1 || true)"
    fi
    [[ -n "$window" ]] && break
    kill -0 "$pid" || { cat "$OUT/office.log"; exit 1; }
    sleep 1
done
test -n "$window" || { xwininfo -root -tree > "$OUT/xwindow-tree.txt"; import -window root "$OUT/office-root.png"; cat "$OUT/xwindow-tree.txt" "$OUT/office.log"; exit 1; }
sleep 5
xdotool getwindowname "$window" > "$OUT/window-title.txt"
import -window "$window" "$OUT/office-window.png"
python3 - "$OUT/office-window.png" <<'PY'
from PIL import Image
import sys
im = Image.open(sys.argv[1]).convert("RGB")
assert im.width >= 400 and im.height >= 300
assert len(set(im.resize((80, 50)).getdata())) > 25
print("PASS: official office editor opened a nonblank window")
PY
