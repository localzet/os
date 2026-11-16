#!/usr/bin/env bash
set -Eeuo pipefail
mode="$1"
export GDK_BACKEND=x11
export ADW_DEBUG_COLOR_SCHEME=prefer-dark ADW_DEBUG_HIGH_CONTRAST=0
case "$mode" in
    dark) ;;
    light) export ADW_DEBUG_COLOR_SCHEME=prefer-light ;;
    contrast) export ADW_DEBUG_HIGH_CONTRAST=1 ;;
    *) exit 2 ;;
esac
work="$(mktemp -d)"
pid=""
wm=""
cleanup() {
    if [[ -n "$pid" ]]; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi
    if [[ -n "$wm" ]]; then kill "$wm" 2>/dev/null || true; wait "$wm" 2>/dev/null || true; fi
    rm -rf -- "$work"
}
trap cleanup EXIT
openbox > "$OUT/window-manager-$mode.log" 2>&1 &
wm=$!
sleep 2
mkdir -p "$work"/{Documents,Projects,Downloads,Pictures}
printf 'Localzet native file manager review\n' > "$work/README.txt"
gsettings set org.gnome.desktop.interface icon-theme Aurora
gsettings set org.gnome.nautilus.icon-view default-zoom-level small-plus
# A dedicated runner-only configuration is not shipped in the image.
mkdir -p "$HOME/.config/gtk-4.0"
printf '[Settings]\ngtk-icon-theme-name=Aurora\n' > "$HOME/.config/gtk-4.0/settings.ini"
nautilus --new-window "$work" > "$OUT/nautilus-$mode.log" 2>&1 &
pid=$!
window=""
for attempt in $(seq 1 40); do
    window="$(xdotool search --onlyvisible --pid "$pid" 2>/dev/null | head -n1 || true)"
    [[ -n "$window" ]] && break
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
done
test -n "$window"
xdotool windowsize "$window" 1000 650
xdotool windowmove "$window" 180 100
xdotool windowfocus --sync "$window"
sleep 2
import -window "$window" "$OUT/nautilus-$mode.png"
python3 - "$OUT/nautilus-$mode.png" "$mode" <<'PY'
import sys
from collections import Counter
from PIL import Image
with Image.open(sys.argv[1]) as im:
    im = im.convert("RGB")
    pixels = Counter(im.getdata())
    assert im.width >= 800 and im.height >= 500, im.size
    counts = [pixels[tuple(bytes.fromhex(c))] for c in ("0e1928", "15243a", "142337")]
    print(sys.argv[2], "Executive palette pixels:", counts)
    if sys.argv[2] == "dark":
        assert all(n > 1000 for n in counts), counts
    else:
        assert all(n < 1000 for n in counts), counts
PY
! grep -Ei 'theme parser error|css parser error|Gtk-CRITICAL|segmentation fault' "$OUT/nautilus-$mode.log"
# Native Nautilus 50 documents Alt+1..9 via win.go-to-tab. Use
# explicit tab indices, not a toolkit-dependent Ctrl+Shift+Tab gesture.
wait_title() {
    local name="$1"
    for attempt in $(seq 1 20); do
        if xdotool getwindowname "$window" | grep -F "$name"; then return 0; fi
        sleep 1
    done
    echo "Expected $name; actual: $(xdotool getwindowname "$window")" >&2
    import -window "$window" "$OUT/nautilus-$mode-navigation-failure.png" || true
    return 1
}
navigate() {
    local name="$1"
    xdotool windowactivate --sync "$window"
    xdotool key --clearmodifiers ctrl+l
    sleep 1
    xdotool type --clearmodifiers "$work/$name"
    xdotool key Return
    wait_title "$name"
}
navigate Documents
xdotool key --clearmodifiers ctrl+t
sleep 3
# Explicitly activate the second tab and wait for focus to settle.
xdotool key --clearmodifiers alt+2
sleep 1
navigate Projects
xdotool key --clearmodifiers alt+1
wait_title Documents
xdotool key --clearmodifiers alt+2
wait_title Projects
import -window "$window" "$OUT/nautilus-$mode-tabs.png"
echo "PASS: $mode palette, navigation and two native tabs"
