#!/usr/bin/env bash
# Run in a disposable Ubuntu 26.04 GNOME 50 runner or VM.
set -Eeuo pipefail

ROOT="$PWD"
OUT="$ROOT/out/gnome-smoke"
SMOKE_ROOT="$(mktemp -d /tmp/localzet-gnome-smoke.XXXXXX)"
UUID=localzet-shell@localzet.com
EXT_SOURCE="$ROOT/extensions/$UUID"

export XDG_DATA_HOME="$SMOKE_ROOT/data"
export XDG_CONFIG_HOME="$SMOKE_ROOT/config"
export XDG_CACHE_HOME="$SMOKE_ROOT/cache"
export XDG_STATE_HOME="$SMOKE_ROOT/state"
export XDG_RUNTIME_DIR="$SMOKE_ROOT/runtime"
export DCONF_PROFILE="$SMOKE_ROOT/dconf-profile"
export HOME="$SMOKE_ROOT/home"
export XDG_SESSION_TYPE=wayland
export XDG_CURRENT_DESKTOP=GNOME
export GDK_BACKEND=x11
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
export GTK_A11Y=none

mkdir -p "$OUT" "$XDG_DATA_HOME/gnome-shell/extensions" "$XDG_DATA_HOME/icons" \
    "$XDG_CONFIG_HOME/dconf" "$XDG_CACHE_HOME" "$XDG_STATE_HOME" "$XDG_RUNTIME_DIR" "$HOME"
chmod 700 "$SMOKE_ROOT" "$XDG_RUNTIME_DIR"
printf 'user-db:user\n' > "$DCONF_PROFILE"

EXT_DEST="$XDG_DATA_HOME/gnome-shell/extensions/$UUID"
cp -R "$EXT_SOURCE" "$EXT_DEST"
glib-compile-schemas --strict "$EXT_DEST/schemas"
cp -a "$ROOT/theme/icons/Localzet" "$XDG_DATA_HOME/icons/"
export EXT_DEST OUT

cleanup() {
    if [[ -n "${xvfb_pid:-}" ]]; then
        kill "$xvfb_pid" 2>/dev/null || true
        wait "$xvfb_pid" 2>/dev/null || true
    fi
    rm -rf -- "$SMOKE_ROOT"
}
trap cleanup EXIT

gnome-shell --version > "$OUT/gnome-shell-version.txt"
cat /etc/os-release > "$OUT/os-release.txt"

for resolution in 1536x1024 1920x1080; do
    export DISPLAY=:99
    Xvfb :99 -screen 0 "${resolution%x*}x${resolution#*x}x24" -nolisten tcp \
        > "$OUT/xvfb-$resolution.log" 2>&1 &
    xvfb_pid=$!
    sleep 2

    export RESOLUTION="$resolution"
    dbus-run-session -- bash -eu <<'GNOME_SESSION'
pipewire > "$OUT/pipewire.log" 2>&1 &
pipewire_pid=$!
wireplumber > "$OUT/wireplumber.log" 2>&1 &
wireplumber_pid=$!
sleep 2

gnome-shell --devkit --wayland > "$OUT/gnome-shell-$RESOLUTION.log" 2>&1 &
shell_pid=$!
cleanup_session() {
    kill "$shell_pid" "$wireplumber_pid" "$pipewire_pid" 2>/dev/null || true
    wait "$shell_pid" 2>/dev/null || true
}
trap cleanup_session EXIT

found=0
for attempt in $(seq 1 30); do
    if ! kill -0 "$shell_pid" 2>/dev/null; then
        echo "GNOME Shell exited before the appearance smoke test" >&2
        cat "$OUT/gnome-shell-$RESOLUTION.log" >&2
        exit 1
    fi
    if gnome-extensions list > "$OUT/extensions-$RESOLUTION.txt" 2>&1 \
            && grep -Fxq localzet-shell@localzet.com "$OUT/extensions-$RESOLUTION.txt"; then
        found=1
        break
    fi
    sleep 2
done
if [[ "$found" != 1 ]]; then
    echo "Localzet Shell was not discoverable in the isolated data directory" >&2
    exit 1
fi

gnome-extensions enable localzet-shell@localzet.com
sleep 8
gnome-extensions list --enabled > "$OUT/enabled-$RESOLUTION.txt"
grep -Fxq localzet-shell@localzet.com "$OUT/enabled-$RESOLUTION.txt"
gsettings set org.gnome.desktop.interface icon-theme "'Localzet'"

for theme in blue purple black; do
    gsettings --schemadir "$EXT_DEST/schemas" set com.localzet.shell appearance "'$theme'"
    sleep 2
    import -window root "$OUT/gnome50-devkit-$RESOLUTION-$theme.png"
done
printf 'GNOME Shell devkit appearance run: %s\n' "$RESOLUTION" >> "$OUT/result.txt"
GNOME_SESSION

if grep -Fq 'JS ERROR:' "$OUT/gnome-shell-$RESOLUTION.log"; then
    echo "GNOME Shell logged a JavaScript error during the appearance smoke" >&2
    grep -F 'JS ERROR:' "$OUT/gnome-shell-$RESOLUTION.log" >&2 || true
    exit 1
fi

    kill "$xvfb_pid" 2>/dev/null || true
    wait "$xvfb_pid" 2>/dev/null || true
    xvfb_pid=
done

python3 - "$OUT" <<'PY'
import sys
from pathlib import Path
from PIL import Image

out = Path(sys.argv[1])
for resolution in ("1536x1024", "1920x1080"):
    expected = tuple(map(int, resolution.split("x")))
    for theme in ("blue", "purple", "black"):
        path = out / f"gnome50-devkit-{resolution}-{theme}.png"
        if not path.is_file():
            raise SystemExit(f"Missing GNOME Shell devkit capture: {path.name}")
        image = Image.open(path).convert("RGB")
        colors = len(set(image.resize((80, 50)).getdata()))
        if image.size != expected or colors < 15:
            raise SystemExit(f"Invalid or blank capture: {path.name} {image.size} {colors}")
        print(f"Captured GNOME Shell devkit {theme}: {image.size}")
PY
