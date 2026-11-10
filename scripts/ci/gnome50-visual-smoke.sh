#!/usr/bin/env bash
# Disposable GitHub runner only. Never run against an existing desktop session.
set -Eeuo pipefail
cd /work
mkdir -p out/gnome-smoke
chmod 777 out/gnome-smoke

useradd --create-home --shell /bin/bash localzet-test
install -d -m 700 -o localzet-test -g localzet-test /tmp/localzet-runtime
install -d -m 755 -o localzet-test -g localzet-test /home/localzet-test/.local/share/gnome-shell/extensions
cp -R extensions/localzet-shell@localzet.com /home/localzet-test/.local/share/gnome-shell/extensions/
chown -R localzet-test:localzet-test /home/localzet-test/.local

Xvfb :99 -screen 0 1440x900x24 -nolisten tcp > out/gnome-smoke/xvfb.log 2>&1 &
xvfb_pid=$!
trap 'kill "$xvfb_pid" 2>/dev/null || true' EXIT
sleep 3

set +e
runuser -u localzet-test -- env \
  HOME=/home/localzet-test USER=localzet-test \
  DISPLAY=:99 XDG_RUNTIME_DIR=/tmp/localzet-runtime \
  XDG_SESSION_TYPE=wayland \
  LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe \
  GDK_BACKEND=x11 \
  dbus-run-session -- bash -c '
    set -u
    gnome-shell --devkit --wayland > /work/out/gnome-smoke/gnome-shell.log 2>&1 &
    shell_pid=$!
    trap "kill $shell_pid 2>/dev/null || true" EXIT
    for i in $(seq 1 36); do
      if ! kill -0 "$shell_pid" 2>/dev/null; then
        echo "GNOME Shell exited early" >&2
        exit 1
      fi
      if gnome-extensions list > /work/out/gnome-smoke/extensions.txt 2>&1; then
        if grep -Fxq "localzet-shell@localzet.com" /work/out/gnome-smoke/extensions.txt; then
          break
        fi
      fi
      sleep 2
    done
    if ! grep -Fxq "localzet-shell@localzet.com" /work/out/gnome-smoke/extensions.txt; then
      echo "Extension not discoverable inside devkit session" >&2
      exit 1
    fi
    gnome-extensions enable localzet-shell@localzet.com
    sleep 15
    gnome-extensions list --enabled > /work/out/gnome-smoke/enabled.txt
    grep -Fxq "localzet-shell@localzet.com" /work/out/gnome-smoke/enabled.txt || exit 1
    echo "Localzet extension enabled in running GNOME Shell devkit" > /work/out/gnome-smoke/result.txt
    sleep 8
  '
result=$?
set -e
# Screenshot must be taken while Xvfb lives. On success, shell may have exited:
# such a frame is diagnostic only, not visual proof.
DISPLAY=:99 import -window root out/gnome-smoke/xvfb-desktop.png || true
python3 - <<'PY'
from pathlib import Path
from PIL import Image
p=Path('out/gnome-smoke/xvfb-desktop.png')
if p.exists():
    im=Image.open(p).convert('RGB')
    samples=set(im.resize((80,50)).getdata())
    print('Screenshot:', im.size, 'sampled unique colors:', len(samples))
else:
    print('No PNG screenshot')
PY
exit "$result"
