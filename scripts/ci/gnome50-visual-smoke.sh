#!/usr/bin/env bash
# Disposable Ubuntu 26.04 GitHub Actions runner only.
set -Eeuo pipefail
ROOT="$PWD"
OUT="$ROOT/out/gnome-smoke"
mkdir -p "$OUT"
UUID=localzet-shell@localzet.com
EXT_SOURCE="$ROOT/extensions/$UUID"
EXT_DEST="$HOME/.local/share/gnome-shell/extensions/$UUID"
if [[ -e "$EXT_DEST" ]]; then
  echo "Refusing to overwrite extension: $EXT_DEST" >&2
  exit 2
fi
mkdir -p "$(dirname "$EXT_DEST")"
cp -R "$EXT_SOURCE" "$EXT_DEST"
if [[ -z "${XDG_RUNTIME_DIR:-}" || ! -d "$XDG_RUNTIME_DIR" ]]; then
  export XDG_RUNTIME_DIR="$(mktemp -d /tmp/localzet-xdg.XXXXXX)"
  chmod 700 "$XDG_RUNTIME_DIR"
fi
export DISPLAY=:99
export XDG_SESSION_TYPE=wayland
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
export GDK_BACKEND=x11
export GTK_A11Y=none
Xvfb :99 -screen 0 1440x900x24 -nolisten tcp > "$OUT/xvfb.log" 2>&1 &
xvfb_pid=$!
trap 'kill "$xvfb_pid" 2>/dev/null || true' EXIT
sleep 3
export OUT
set +e
dbus-run-session -- bash -c '
  set -u
  # Mutter devkit displays the nested desktop through PipeWire.
  pipewire > "$OUT/pipewire.log" 2>&1 &
  pipewire_pid=$!
  wireplumber > "$OUT/wireplumber.log" 2>&1 &
  wireplumber_pid=$!
  trap "kill $pipewire_pid $wireplumber_pid 2>/dev/null || true" EXIT
  sleep 3
  LOCALZET_EXPERIMENTAL_GLASS=1 gnome-shell --devkit --wayland > "$OUT/gnome-shell.log" 2>&1 &
  shell_pid=$!
  trap "kill $shell_pid 2>/dev/null || true" EXIT
  for i in $(seq 1 30); do
    if ! kill -0 "$shell_pid" 2>/dev/null; then
      echo "GNOME Shell exited early" >&2
      exit 1
    fi
    if gnome-extensions list > "$OUT/extensions.txt" 2>&1 && grep -Fxq localzet-shell@localzet.com "$OUT/extensions.txt"; then
      break
    fi
    sleep 2
  done
  grep -Fxq localzet-shell@localzet.com "$OUT/extensions.txt" || { echo "Extension undiscoverable" >&2; exit 1; }
  gnome-extensions enable localzet-shell@localzet.com
  gnome-extensions enable ubuntu-appindicators@ubuntu.com || exit 1
  # Use the actual shipped wallpaper and leave the startup overview before
  # capturing. The devkit's default blue test background is not Aurora.
  wallpaper="file://$PWD/assets/wallpapers/aurora.svg"
  gsettings set org.gnome.desktop.background picture-uri "$wallpaper" || exit 1
  gsettings set org.gnome.desktop.background picture-uri-dark "$wallpaper" || exit 1
  gsettings set org.gnome.desktop.interface color-scheme prefer-dark || exit 1
  sleep 16
  xdotool search --name "Mutter Development Kit" windowactivate --sync key Escape || exit 1
  sleep 3
  gnome-extensions list --enabled > "$OUT/enabled.txt"
  grep -Fxq localzet-shell@localzet.com "$OUT/enabled.txt" || { echo "Not enabled" >&2; exit 1; }
  gnome-extensions list --active | grep -Fx localzet-shell@localzet.com || exit 1
  grep -F "Localzet Glass: panel background effect active" "$OUT/gnome-shell.log" || exit 1
  import -window root "$OUT/aurora-panel-experimental.png" || exit 1
  cp "$OUT/aurora-panel-experimental.png" "$OUT/gnome-running.png" || exit 1
  # Exercise teardown/re-enable, including the accessibility fallback.
  gsettings set org.gnome.desktop.a11y.interface high-contrast true || exit 1
  sleep 2
  import -window root "$OUT/aurora-panel-high-contrast.png" || exit 1
  gsettings set org.gnome.desktop.a11y.interface high-contrast false || exit 1
  gnome-extensions disable localzet-shell@localzet.com || exit 1
  sleep 2
  gnome-extensions enable localzet-shell@localzet.com || exit 1
  sleep 3
  gnome-extensions list --active | grep -Fx localzet-shell@localzet.com || exit 1
  test "$(grep -Fc "Localzet Glass: panel background effect active" "$OUT/gnome-shell.log")" -ge 2 || exit 1
  gnome-extensions list --active | grep -Fx ubuntu-appindicators@ubuntu.com || exit 1
  gdbus call --session --dest org.kde.StatusNotifierWatcher --object-path /StatusNotifierWatcher --method org.freedesktop.DBus.Properties.Get org.kde.StatusNotifierWatcher IsStatusNotifierHostRegistered | grep -F true || exit 1
  # The official Qt client registers its own tray menu. Do not create a second
  # paired identity or fake the connection/battery state.
  nectar_data="$(mktemp -d)"
  QT_QPA_PLATFORM=xcb QT_QUICK_BACKEND=software LC_ALL=C.UTF-8 \
    /usr/bin/nectarlink-desktop --data-dir "$nectar_data" > "$OUT/nectarlink.log" 2>&1 &
  nectar_pid=$!
  trap "kill $nectar_pid $shell_pid $pipewire_pid $wireplumber_pid 2>/dev/null || true; wait $nectar_pid 2>/dev/null || true; rm -rf -- \"$nectar_data\"" EXIT
  if ! python3 "$PWD/scripts/ci/check-nectarlink-tray.py" > "$OUT/nectarlink-tray.txt" 2>&1; then
    cat "$OUT/nectarlink-tray.txt"
    exit 1
  fi
  cat "$OUT/nectarlink-tray.txt"
  import -window root "$OUT/gnome-running.png"
  # Do not upload private node identity even from an ephemeral test.
  kill "$nectar_pid" 2>/dev/null || true
  wait "$nectar_pid" 2>/dev/null || true
  rm -rf -- "$nectar_data"
  echo "GNOME Shell devkit running with Localzet Shell enabled" > "$OUT/result.txt"
'
rc=$?
set -e
DISPLAY=:99 import -window root "$OUT/after-exit.png" || true
python3 - "$OUT/gnome-running.png" <<'PY'
import sys
from pathlib import Path
from PIL import Image
p=Path(sys.argv[1])
if not p.exists():
    print('No live GNOME screenshot')
    sys.exit(2)
im=Image.open(p).convert('RGB')
colors=len(set(im.resize((80,50)).getdata()))
print('Captured:', im.size, 'downsampled distinct colors:', colors)
if colors < 15:
    print('Image appears blank; not visual verification')
    sys.exit(2)
PY
exit "$rc"
