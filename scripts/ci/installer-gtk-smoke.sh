#!/usr/bin/env bash
set -Eeuo pipefail
mkdir -p out/installer
export PYTHONPATH="$PWD/src"
export GDK_BACKEND=x11
export GSK_RENDERER=cairo
dbus-run-session -- bash -eu -c '
    python3 -m localzet.installer.app > out/installer/application.log 2>&1 &
    pid=$!
    trap "kill \"$pid\" 2>/dev/null || true" EXIT
    for attempt in $(seq 1 30); do
        kill -0 "$pid" || { cat out/installer/application.log; exit 1; }
        if xdotool search --name "Установка Localzet OS" > out/installer/windows.txt 2>/dev/null; then
            sleep 2
            import -window root out/installer/window.png
            exit 0
        fi
        sleep 1
    done
    cat out/installer/application.log
    exit 1
'
