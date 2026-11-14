#!/usr/bin/env bash
set -Eeuo pipefail
export PYTHONPATH="$PWD/src" GDK_BACKEND=x11 GSK_RENDERER=cairo GTK_A11Y=none
export OUT="$PWD/out/containers-gtk"
mkdir -p "$OUT"
# Do not install/start an engine to make this test pass.
xvfb-run -a -s '-screen 0 1440x900x24' dbus-run-session -- bash -s <<'GTK_TEST'
set -Eeuo pipefail
gsettings set org.gnome.desktop.interface color-scheme prefer-dark
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
kill -0 "$pid"
! grep -q 'Traceback (most recent call last)' "$OUT/app.log"
GTK_TEST
