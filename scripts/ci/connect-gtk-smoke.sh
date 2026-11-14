#!/usr/bin/env bash
# Run only on disposable CI Xvfb. Verify the real GTK window opens.
set -Eeuo pipefail
mkdir -p out/connect
export GDK_BACKEND=x11
export GSK_RENDERER=cairo
export PYTHONPATH="$PWD/src"
dbus-run-session -- bash -eu -c '
  python3 -m localzet.connect_app > out/connect/application.log 2>&1 &
  app_pid=$!
  trap "kill \"$app_pid\" 2>/dev/null || true" EXIT
  found=0
  for i in $(seq 1 30); do
    if ! kill -0 "$app_pid" 2>/dev/null; then
      echo "Localzet Connect exited before creating a window" >&2
      cat out/connect/application.log >&2
      exit 1
    fi
    if xdotool search --name "Localzet Connect" > out/connect/windows.txt 2>/dev/null; then
      found=1
      break
    fi
    sleep 1
  done
  if [ "$found" != 1 ]; then
    echo "No Localzet Connect X11 window found" >&2
    cat out/connect/application.log >&2
    exit 1
  fi
  sleep 3
  import -window root out/connect/live-window.png
  python3 - <<'"'"'PY'"'"'
from pathlib import Path
from PIL import Image
im = Image.open("out/connect/live-window.png").convert("RGB")
if im.width < 900 or im.height < 600:
    raise SystemExit("Unexpected framebuffer size")
if len(set(im.resize((80, 50)).getdata())) < 20:
    raise SystemExit("Blank/undrawn GTK window")
print("GTK window captured", im.size)
PY
'