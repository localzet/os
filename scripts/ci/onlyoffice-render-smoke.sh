#!/usr/bin/env bash
# Real, unprivileged editor in an isolated X11 or nested Wayland session.
# No sandbox-disabling switches. Each mode gets a disposable user profile.
set -Eeuo pipefail
[[ $EUID != 0 && ${LOCALZET_DISPOSABLE_VM:-} == 1 ]]
mode="$1"
case "$mode" in default|software) ;; *) exit 2 ;; esac
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
out="$repo/out/office-render/$mode"
mkdir -p "$out"
work="$(mktemp -d)"
pid=""
wm=""
cleanup() {
    if [[ -n "$pid" ]]; then kill -TERM -- "-$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi
    if [[ -n "$wm" ]]; then kill "$wm" 2>/dev/null || true; wait "$wm" 2>/dev/null || true; fi
    rm -rf -- "$work"
}
trap cleanup EXIT
export HOME="$work/home" XDG_CONFIG_HOME="$work/config" XDG_DATA_HOME="$work/data" XDG_CACHE_HOME="$work/cache"
mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_CACHE_HOME"
export QT_QPA_PLATFORM=xcb GDK_BACKEND=x11
export LANG=C.UTF-8
# Software mode is a scoped diagnostic, not a distribution default.
flags=()
if [[ "$mode" == software ]]; then
    export LIBGL_ALWAYS_SOFTWARE=1 QT_OPENGL=software
    flags=(--disable-gpu)
fi
openbox > "$out/openbox.log" 2>&1 &
wm=$!
sleep 2
python3 "$repo/scripts/ci/office-fixture.py" "$work/Localzet-offline-review.docx"
glxinfo -B > "$out/graphics.txt" 2>&1 || true
# Diagnose loader failures directly, without waiting for a window that
# cannot appear. Use the application's bundled library directory.
LD_LIBRARY_PATH=/opt/onlyoffice/desktopeditors ldd /opt/onlyoffice/desktopeditors/DesktopEditors > "$out/loader.txt"
if grep -F 'not found' "$out/loader.txt"; then exit 1; fi
setsid /usr/bin/onlyoffice-desktopeditors "${flags[@]}" "$work/Localzet-offline-review.docx" > "$out/editor.log" 2>&1 &
pid=$!
window=""
for attempt in $(seq 1 90); do
    window="$(xdotool search --onlyvisible --name 'Localzet-offline-review' 2>/dev/null | tail -n1 || true)"
    [[ -n "$window" ]] && break
    if ! kill -0 "$pid" 2>/dev/null; then
        cat "$out/editor.log"
        exit 1
    fi
    sleep 1
done
if [[ -z "$window" ]]; then
    xwininfo -root -tree > "$out/window-tree.txt" || true
    import -window root "$out/root.png" || true
    cat "$out/editor.log"
    exit 1
fi
xdotool windowactivate --sync "$window"
xdotool windowsize "$window" 1100 760
xdotool windowmove "$window" 80 60
xdotool getwindowname "$window" > "$out/window-title.txt"
rendered=0
for attempt in $(seq 1 25); do
    sleep 3
    import -window "$window" "$out/document.png"
    if python3 - "$repo" "$out/document.png" <<'PY' | tee "$out/metrics.txt"
import importlib.util
from pathlib import Path
import sys
spec = importlib.util.spec_from_file_location("evidence", Path(sys.argv[1]) / "scripts/visual-evidence.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
from PIL import Image
path = Path(sys.argv[2])
with Image.open(path) as im:
    w,h = im.size
# Ignore titlebar, window border and side panels. Inspect actual editor.
metrics = module.visual_metrics(path, (w//10, h//10, w*8//10, h*8//10))
ink = module.document_ink(path)
print(metrics, "fixture heading ink:", ink)
raise SystemExit(0 if module.meaningful(metrics) and ink >= 250 else 1)
PY
    then
        echo "PASS: $mode native offline document window rendered nonblank content"
        rendered=1
        break
    fi
done
if [[ "$rendered" != 1 ]]; then
    echo "FAIL: $mode editor never produced meaningful document pixels" >&2
    exit 1
fi

# Exercise an actual edit/save/reopen cycle, not just window creation.
marker="LOCALZET OFFICE ROUNDTRIP"
xdotool mousemove --window "$window" 520 520 click 1
xdotool key --clearmodifiers ctrl+End
xdotool key --clearmodifiers Return
xdotool type --clearmodifiers --delay 35 "$marker"
xdotool key --clearmodifiers ctrl+s
python3 - "$work/Localzet-offline-review.docx" "$marker" <<'PY'
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import sys
import time

path = Path(sys.argv[1])
marker = sys.argv[2]
for _ in range(30):
    try:
        with ZipFile(path) as archive:
            document = archive.read("word/document.xml").decode("utf-8")
        if marker in document:
            print("PASS: ONLYOFFICE saved the edited DOCX payload")
            break
    except (BadZipFile, KeyError, OSError):
        pass
    time.sleep(1)
else:
    raise SystemExit("FAIL: edited DOCX marker was not persisted")
PY

# Close the first editor process completely so the second launch cannot
# forward to an already-running instance with a stale document state.
xdotool key --clearmodifiers ctrl+q || true
sleep 3
if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill -TERM -- "-$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
fi
pid=""
setsid /usr/bin/onlyoffice-desktopeditors "${flags[@]}" "$work/Localzet-offline-review.docx" > "$out/reopen-editor.log" 2>&1 &
pid=$!
window=""
for attempt in $(seq 1 60); do
    window="$(xdotool search --onlyvisible --name 'Localzet-offline-review' 2>/dev/null | tail -n1 || true)"
    [[ -n "$window" ]] && break
    if ! kill -0 "$pid" 2>/dev/null; then
        cat "$out/reopen-editor.log"
        exit 1
    fi
    sleep 1
done
test -n "$window" || { xwininfo -root -tree > "$out/reopen-window-tree.txt"; cat "$out/reopen-editor.log"; exit 1; }
xdotool windowactivate --sync "$window"
xdotool key --clearmodifiers ctrl+End
sleep 3
import -window "$window" "$out/reopened-document.png"
tesseract "$out/reopened-document.png" stdout --psm 6 2>/dev/null > "$out/reopened-document.txt"
grep -Fq "$marker" "$out/reopened-document.txt"
echo "PASS: saved DOCX reopened and the edited text is visible"
