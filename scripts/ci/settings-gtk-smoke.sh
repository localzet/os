#!/usr/bin/env bash
# Run only on disposable CI Xvfb. Verify the real GTK window opens.
set -Eeuo pipefail
mkdir -p out/settings
export GDK_BACKEND=x11
export GSK_RENDERER=cairo
export PYTHONPATH="$PWD/src"
dbus-run-session -- bash -eu -c '
  python3 -m localzet.settings.app > out/settings/application.log 2>&1 &
  app_pid=$!
  trap "kill \"$app_pid\" 2>/dev/null || true" EXIT
  found=0
  for i in $(seq 1 30); do
    if ! kill -0 "$app_pid" 2>/dev/null; then
      echo "Localzet Settings exited before creating a window" >&2
      cat out/settings/application.log >&2
      exit 1
    fi
    if xdotool search --name "Localzet Settings" > out/settings/windows.txt 2>/dev/null; then
      found=1
      break
    fi
    sleep 1
  done
  if [ "$found" != 1 ]; then
    echo "No Localzet Settings X11 window found" >&2
    cat out/settings/application.log >&2
    exit 1
  fi
  sleep 3
  import -window root out/settings/live-window.png
  window=$(head -n 1 out/settings/windows.txt)
  xdotool windowfocus --sync "$window" key ctrl+2
  sleep 2
  grep -F "Localzet Settings: page=modules" out/settings/application.log
  import -window root out/settings/modules.png
  xdotool key ctrl+3
  sleep 2
  grep -F "Localzet Settings: page=system" out/settings/application.log
  import -window root out/settings/system.png
  xdotool key ctrl+1
  sleep 1
  test "$(grep -F "Localzet Settings: page=" out/settings/application.log | tail -n 1)" = "Localzet Settings: page=home"
  ! grep -E "Traceback|Gtk-CRITICAL|Theme parser error" out/settings/application.log
  python3 - <<'"'"'PY'"'"'
from pathlib import Path
from PIL import Image
im = Image.open("out/settings/live-window.png").convert("RGB")
if im.width < 900 or im.height < 600:
    raise SystemExit("Unexpected framebuffer size")
if len(set(im.resize((80, 50)).getdata())) < 20:
    raise SystemExit("Blank/undrawn GTK window")
from collections import Counter
pixels = Counter(im.getdata())
for color in ("091321", "101b2d"):
    count = pixels[tuple(bytes.fromhex(color))]
    print("Midnight", color, "pixels:", count)
    if count < 1000:
        raise SystemExit("Missing actual Midnight surface: " + color)
# Secondary text must not fade into the card background.
secondary = pixels[tuple(bytes.fromhex("b8c9dd"))]
print("Executive secondary text pixels:", secondary)
if secondary < 20:
    raise SystemExit("Secondary text did not render with the intended contrast")
print("GTK window captured", im.size)
PY
'