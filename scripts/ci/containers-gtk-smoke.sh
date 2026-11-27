#!/usr/bin/env bash
set -Eeuo pipefail
export PYTHONPATH="$PWD/src" GDK_BACKEND=x11 GSK_RENDERER=cairo GTK_A11Y=none
export OUT="$PWD/out/containers-gtk"
mkdir -p "$OUT"
# Do not install/start an engine to make this test pass.
xvfb-run -a -s '-screen 0 1440x900x24' dbus-run-session -- bash -s <<'GTK_TEST'
set -Eeuo pipefail
pids=()
cleanup() {
    for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT

ADW_DEBUG_COLOR_SCHEME=prefer-dark python3 -m localzet.containers_app > "$OUT/app-dark.log" 2>&1 &
pid=$!
pids+=("$pid")
window=""
for attempt in $(seq 1 30); do
    kill -0 "$pid" || { cat "$OUT/app-dark.log"; exit 1; }
    window="$(xdotool search --onlyvisible --name 'Localzet Containers' | head -n1 || true)"
    [[ -n "$window" ]] && break
    sleep 1
done
test -n "$window"
sleep 3
import -window "$window" "$OUT/window.png"
dark_level="$(convert "$OUT/window.png" -format '%[fx:p{500,300}.r+p{500,300}.g+p{500,300}.b]' info:)"
awk -v value="$dark_level" 'BEGIN { exit !(value < 0.6) }' || {
    echo "Expected the GNOME prefer-dark surface, got RGB sum $dark_level" >&2
    exit 1
}
# Exercise actual persistent navigation, even with no Docker daemon.
for page in 2 3 4 5 1; do
    xdotool windowfocus "$window" key "ctrl+$page"
    sleep 2
    case "$page" in
        1) title="Контейнеры";;
        2) title="Compose";;
        3) title="Образы";;
        4) title="Тома";;
        5) title="Сети";;
    esac
    xdotool getwindowname "$window" | grep -F "$title"
    import -window "$window" "$OUT/page-$page.png"
    kill -0 "$pid"
done

kill "$pid"
wait "$pid" || true
pids=()
ADW_DEBUG_COLOR_SCHEME=prefer-light python3 -m localzet.containers_app > "$OUT/app-light.log" 2>&1 &
light_pid=$!
pids+=("$light_pid")
light_window=""
for attempt in $(seq 1 30); do
    kill -0 "$light_pid" || { cat "$OUT/app-light.log"; exit 1; }
    light_window="$(xdotool search --onlyvisible --name 'Localzet Containers' | head -n1 || true)"
    [[ -n "$light_window" ]] && break
    sleep 1
done
test -n "$light_window"
sleep 3
import -window "$light_window" "$OUT/window-light.png"
light_level="$(convert "$OUT/window-light.png" -format '%[fx:p{500,300}.r+p{500,300}.g+p{500,300}.b]' info:)"
awk -v value="$light_level" 'BEGIN { exit !(value > 2.0) }' || {
    echo "Explicit GNOME light preference was not applied; RGB sum $light_level" >&2
    exit 1
}
kill -0 "$light_pid"
! grep -q 'Traceback (most recent call last)' "$OUT/app-dark.log" "$OUT/app-light.log"
GTK_TEST
