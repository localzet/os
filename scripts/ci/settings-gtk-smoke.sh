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
# Match the current owner-approved Aurora Professional Violet × Ember
# surfaces, not the superseded Soft Graphite palette.
required = {
    "10091E": 10000,  # deep window background
    "28183F": 1000,   # sidebar/card surface
    "34234F": 1000,   # elevated rows and controls
    "6436B5": 100,    # selected navigation
    "F4EEFF": 100,    # primary foreground
    "B9A5D5": 20,     # secondary foreground
}
for color, minimum in required.items():
    count = pixels[tuple(bytes.fromhex(color))]
    print("Aurora Professional", "#" + color, "pixels:", count)
    if count < minimum:
        raise SystemExit("Missing actual Aurora Professional surface/text: #" + color)
print("GTK window captured", im.size)
PY
'