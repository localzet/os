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
mkdir -p "$HOME/.local/share/icons"
python3 "$ROOT/scripts/build-aurora-icons.py" "$HOME/.local/share/icons"
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
dbus-run-session -- bash -s <<'GNOME_TEST'
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
  trap "kill $shell_pid $pipewire_pid $wireplumber_pid 2>/dev/null || true" EXIT
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
  gsettings set org.gnome.desktop.interface icon-theme Aurora || exit 1
  install -D -m 0644 "$PWD/assets/terminal/aurora.palette" "$HOME/.local/share/org.gnome.Ptyxis/palettes/aurora.palette" || exit 1
  profile=4e6f25d9af1244aa896f5b028bf7a020
  gsettings set org.gnome.Ptyxis profile-uuids "['$profile']" || exit 1
  gsettings set org.gnome.Ptyxis default-profile-uuid "$profile" || exit 1
  # The nested devkit lacks the full desktop settings portal. Test the dark
  # palette explicitly here; the installed system follows the system preference.
  gsettings set org.gnome.Ptyxis interface-style dark || exit 1
  gsettings set "org.gnome.Ptyxis.Profile:/org/gnome/Ptyxis/Profiles/$profile/" palette xterm || exit 1
  gsettings set "org.gnome.Ptyxis.Profile:/org/gnome/Ptyxis/Profiles/$profile/" label Aurora || exit 1
  gsettings set org.gnome.shell favorite-apps "['org.gnome.Nautilus.desktop', 'org.gnome.Ptyxis.desktop', 'google-chrome.desktop', 'firefox.desktop']" || exit 1
  test "$(gsettings get org.gnome.desktop.interface icon-theme)" = "'Aurora'" || exit 1
  sleep 16
  # Xvfb has no outer window manager; use direct focus rather than EWMH.
  xwininfo -root -tree > "$OUT/xwindows.txt"
  window="$(xdotool search --onlyvisible --name 'Mutter|GNOME Shell' | head -n 1)"
  if [[ -z "$window" ]]; then
    cat "$OUT/xwindows.txt"
    echo "No nested compositor window" >&2
    exit 1
  fi
  xdotool windowfocus --sync "$window" key Escape || exit 1
  sleep 3
  gnome-extensions list --enabled > "$OUT/enabled.txt"
  grep -Fxq localzet-shell@localzet.com "$OUT/enabled.txt" || { echo "Not enabled" >&2; exit 1; }
  gnome-extensions list --active | grep -Fx localzet-shell@localzet.com || exit 1
  grep -F "Localzet Glass: panel background effect active" "$OUT/gnome-shell.log" || exit 1
  grep -F "Localzet Panel: executive navigation ready" "$OUT/gnome-shell.log" || exit 1
  import -window root "$OUT/aurora-panel-experimental.png" || exit 1
  cp "$OUT/aurora-panel-experimental.png" "$OUT/gnome-running.png" || exit 1
  # Devkit window content starts under its title bar; use the actual
  # dock position reported by the extension, not fixed monitor coordinates.
  dock="$(sed -n 's/.*Localzet Launcher: dock=\([0-9]*,[0-9]*\).*/\1/p' "$OUT/gnome-shell.log" | tail -n 1)"
  test -n "$dock" || exit 1
  IFS=, read -r dock_x dock_y <<< "$dock"
  xdotool mousemove --window "$window" "$((dock_x + 33))" "$((dock_y + 75))" click 1 || exit 1
  sleep 3
  grep -F "Localzet Launcher: opened" "$OUT/gnome-shell.log" || exit 1
  import -window root "$OUT/aurora-launcher.png" || exit 1
  xdotool type --clearmodifiers ptyxis || exit 1
  sleep 2
  grep -F "Localzet Launcher: results=1" "$OUT/gnome-shell.log" || exit 1
  import -window root "$OUT/aurora-launcher-search.png" || exit 1
  xdotool key Return || exit 1
  sleep 5
  grep -F "Localzet Launcher: activated org.gnome.Ptyxis.desktop" "$OUT/gnome-shell.log" || exit 1
  pgrep -x ptyxis || exit 1
  # Startup may report RUNNING before the first window is mapped.
  for attempt in $(seq 1 30); do
    if grep -F "Localzet Dock: running=" "$OUT/gnome-shell.log" | tail -n 1 | grep -Eq "running=[1-9][0-9]* items=[1-9][0-9]* focused=1$"; then break; fi
    sleep 1
  done
  grep -F "Localzet Dock: running=" "$OUT/gnome-shell.log" | tail -n 1 | grep -E "running=[1-9][0-9]* items=[1-9][0-9]* focused=1$" || exit 1
  import -window root "$OUT/aurora-dock-running.png" || exit 1
  # Verify the built-in XTerm palette using actual ANSI background swatches.
  # Black pixels alone would also match the compositor's outer background.
  xdotool type --clearmodifiers --delay 1 "printf '\\033[41m        \\033[42m        \\033[43m        \\033[44m        \\033[45m        \\033[46m        \\033[0m\\n'" || exit 1
  xdotool key Return || exit 1
  sleep 2
  import -window root "$OUT/aurora-terminal-xterm.png" || exit 1
  python3 - "$OUT/aurora-terminal-xterm.png" <<'PY' || exit 1
import sys
from collections import Counter
from PIL import Image
# XTerm's built-in ANSI colors (Ptyxis 50), not a copied palette file.
with Image.open(sys.argv[1]) as screenshot:
    counts = Counter(screenshot.convert("RGB").getdata())
for color in ("cd0000", "00cd00", "cdcd00", "0000ee", "cd00cd", "00cdcd"):
    rgb = tuple(bytes.fromhex(color))
    print("XTerm ANSI background", color, "pixels:", counts[rgb])
    if counts[rgb] < 100:
        raise SystemExit("XTerm terminal palette did not render: " + color)
PY
  pkill -x ptyxis || true
  sleep 5
  grep -F "Localzet Dock: running=" "$OUT/gnome-shell.log" | tail -n 1 | grep -E "running=0 items=[1-9][0-9]* focused=0$" || exit 1
  import -window root "$OUT/aurora-dock-idle.png" || exit 1
  # The panel is still the real GNOME panel. Exercise the real menus and
  # deliver an original notification through the session's standard bus.
  grep -F "Localzet Surfaces: native menus=2" "$OUT/gnome-shell.log" || exit 1
  width=$(xdotool getwindowgeometry --shell "$window" | sed -n 's/^WIDTH=//p')
  xdotool mousemove --window "$window" "$((width - 44))" 58 click 1 || exit 1
  sleep 3
  grep -F "Localzet Surfaces: opened quickSettings" "$OUT/gnome-shell.log" || exit 1
  import -window root "$OUT/aurora-quick-settings.png" || exit 1
  xdotool key Escape || exit 1
  sleep 2
  notify-send --app-name="Localzet" "Aurora" "Проверка уведомлений" || exit 1
  sleep 2
  xdotool mousemove --window "$window" "$((width / 2))" 58 click 1 || exit 1
  sleep 3
  grep -F "Localzet Surfaces: opened dateMenu" "$OUT/gnome-shell.log" || exit 1
  import -window root "$OUT/aurora-notifications.png" || exit 1
  xdotool key Escape || exit 1
  sleep 2
  xdotool windowfocus --sync "$window" key super+a || exit 1
  sleep 5
  import -window root "$OUT/aurora-app-grid.png" || exit 1
  xdotool windowfocus --sync "$window" key Escape || exit 1
  sleep 3
  xdotool windowfocus --sync "$window" key Escape || exit 1
  sleep 3
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
GNOME_TEST
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
