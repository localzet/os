#!/usr/bin/env bash
set -Eeuo pipefail
mode="$1"
export GDK_BACKEND=x11 GSK_RENDERER=cairo
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
for name in build-notes.txt release-notes.md manifest.json packages.tsv screenshot-review.txt; do
    printf 'Original Localzet test fixture\n' > "$work/$name"
done
gsettings set org.gnome.desktop.interface icon-theme Aurora
gsettings set org.gnome.nautilus.icon-view default-zoom-level small-plus
gsettings set org.gnome.nautilus.preferences default-folder-viewer icon-view
# A dedicated runner-only configuration is not shipped in the image.
mkdir -p "$HOME/.config/gtk-4.0"
printf '[Settings]\ngtk-icon-theme-name=Aurora\n' > "$HOME/.config/gtk-4.0/settings.ini"
start_window() {
    local view="$1" directory="$2"
    gsettings set org.gnome.nautilus.preferences default-folder-viewer "$view"
    test "$(gsettings get org.gnome.nautilus.preferences default-folder-viewer)" = "'$view'"
    # Use a fresh process so the view preference is read on construction.
    nautilus --new-window "$directory" >> "$OUT/nautilus-$mode.log" 2>&1 &
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
    xdotool windowactivate --sync "$window"
    sleep 3
}
stop_window() {
    if [[ -n "$pid" ]]; then
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
        pid=""
    fi
    sleep 2
}
capture_window() {
    local output="$1"
    for attempt in $(seq 1 15); do
        kill -0 "$pid"
        import -window "$window" "$output"
        if python3 - "$output" <<'PY'
import sys
from PIL import Image, ImageStat
with Image.open(sys.argv[1]) as im:
    rgb = im.convert("RGB")
    assert rgb.width >= 800 and rgb.height >= 500, rgb.size
    assert max(ImageStat.Stat(rgb).stddev) > 8, "Flat frame"
    assert len(rgb.getcolors(maxcolors=1000000) or range(1000000)) >= 64, "Insufficient rendered detail"
PY
        then return 0; fi
        sleep 1
    done
    echo "Nautilus did not paint its managed window" >&2
    return 1
}
start_window icon-view "$work"
capture_window "$OUT/nautilus-$mode.png"
python3 - "$OUT/nautilus-$mode.png" "$mode" <<'PY'
import sys
from collections import Counter
from PIL import Image
with Image.open(sys.argv[1]) as im:
    im = im.convert("RGB")
    pixels = Counter(im.getdata())
    assert im.width >= 800 and im.height >= 500, im.size
    counts = [pixels[tuple(bytes.fromhex(c))] for c in ("10091E", "28183F", "34234F")]
    print(sys.argv[2], "Aurora Violet × Ember palette pixels:", counts)
    if sys.argv[2] == "dark":
        assert all(n > 1000 for n in counts), counts
    else:
        assert all(n < 1000 for n in counts), counts
PY
! grep -Ei 'theme parser error|css parser error|Gtk-CRITICAL|segmentation fault' "$OUT/nautilus-$mode.log"
# Capture a separately constructed native list view. The earlier Ctrl+2
# shortcut produced identical grid screenshots even after six attempts.
# Use a fresh folder (no saved folder metadata), containing the same data.
list_root="$work/list-fixture"
mkdir -p "$list_root"/{Documents,Projects,Downloads,Pictures}
cp "$work"/*.txt "$work"/*.md "$work"/*.json "$work"/*.tsv "$list_root/"
stop_window
start_window list-view "$list_root"
capture_window "$OUT/nautilus-$mode-list.png"
python3 - "$OUT/nautilus-$mode.png" "$OUT/nautilus-$mode-list.png" "$mode" <<'PY'
from PIL import Image, ImageChops, ImageStat
from collections import Counter
import sys
grid = Image.open(sys.argv[1]).convert("RGB")
view = Image.open(sys.argv[2]).convert("RGB")
assert grid.size == view.size, (grid.size, view.size)
w,h = view.size
region = (int(w*.21), int(h*.08), int(w*.97), int(h*.9))
diff = ImageStat.Stat(ImageChops.difference(grid.crop(region), view.crop(region))).mean
print("Grid/list content mean absolute RGB difference:", diff)
assert max(diff) > 3, "List screenshot is still the grid"
if sys.argv[3] == "dark":
    pixels = Counter(view.getdata())
    assert pixels[(16,9,30)] > 1000 and pixels[(40,24,63)] > 1000
    # GTK ColumnView headings are dimmed upstream. The Violet overlay must
    # restore readable metadata rather than merely pass surface-color checks.
    background = (16, 9, 30)
    def luminance(rgb):
        values = []
        for value in rgb:
            value = value / 255
            values.append(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4)
        return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]
    def contrast(foreground, background):
        first, second = sorted((luminance(foreground), luminance(background)), reverse=True)
        return (first + 0.05) / (second + 0.05)
    header_regions = {
        "Name": (int(w*.22), int(h*.07), int(w*.33), int(h*.14)),
        "Size": (int(w*.78), int(h*.07), int(w*.86), int(h*.14)),
        "Modified": (int(w*.86), int(h*.07), int(w*.98), int(h*.14)),
    }
    for label, region in header_regions.items():
        ratios = [contrast(pixel, background) for pixel in view.crop(region).getdata()
                  if sum(abs(pixel[i] - background[i]) for i in range(3)) >= 45]
        assert len(ratios) >= 10, (label, len(ratios))
        ratios.sort()
        p90 = ratios[int(.90 * (len(ratios) - 1))]
        print(f"{label} header text 90th-percentile contrast: {p90:.2f}:1")
        assert p90 >= 4.5, (label, p90)
    # The actual grid has folder glyphs centered around x=280,407,...
    # List icons must occupy multiple vertical rows near the sidebar.
    # Search a broad strip, then cluster contiguous nonempty scan lines.
    rows = []
    for y in range(int(h*.10), int(h*.85)):
        n = sum(b > r+30 and b > g+12 and g > r+10
                for r,g,b in (view.getpixel((x,y)) for x in range(int(w*.205),int(w*.31))))
        if n >= 4:
            rows.append(y)
    bands = []
    for y in rows:
        if not bands or y > bands[-1][-1]+2:
            bands.append([y])
        else:
            bands[-1].append(y)
    bands = [band for band in bands if len(band) >= 3]
    print("Native list blue folder bands:", [(b[0],b[-1]) for b in bands])
    assert len(bands) >= 4, "No four separate folder rows"
PY
echo "PASS: $mode independently launched native list view"
# Keep the native list open for navigation and tab tests.
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
    # Paste one complete URI after selecting the current entry. Typing
    # character-by-character races Nautilus' async path autocompletion.
    xdotool key --clearmodifiers ctrl+a
    printf '%s' "$list_root/$name" | xclip -selection clipboard
    xdotool key --clearmodifiers ctrl+v
    sleep 1
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
capture_window "$OUT/nautilus-$mode-tabs.png"
! grep -Ei 'theme parser error|css parser error|Gtk-CRITICAL|segmentation fault' "$OUT/nautilus-$mode.log"
echo "PASS: $mode palette, grid, list, navigation and two native tabs"
