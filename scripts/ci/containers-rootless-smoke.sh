#!/usr/bin/env bash
# Dedicated disposable runner only. Never fall back to the system daemon.
set -Eeuo pipefail
[[ ${LOCALZET_DISPOSABLE_VM:-} == 1 && $EUID != 0 ]]
export PYTHONPATH="$PWD/src"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
out="$PWD/out/containers-rootless"
mkdir -p "$out"
socket="$XDG_RUNTIME_DIR/docker.sock"
[[ ! -e "$socket" && ! -L "$socket" ]]
work="$(mktemp -d)"
unit="localzet-rootless-ci-$$"
cleanup() {
    systemctl --user stop "$unit.service" || true
    systemctl --user reset-failed "$unit.service" || true
    rm -rf -- "$work"
}
trap cleanup EXIT
command -v dockerd-rootless.sh
systemd-run --user --unit="$unit" --property=Delegate=yes \
    --setenv="XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR" \
    "$(command -v dockerd-rootless.sh)" --host="unix://$socket" \
    --data-root="$work/data" --exec-root="$work/exec" --pidfile="$work/docker.pid" \
    --storage-driver=vfs
for i in $(seq 1 60); do
    if /usr/bin/docker --host "unix://$socket" info > "$out/engine.txt" 2>&1; then break; fi
    sleep 2
done
/usr/bin/docker --host "unix://$socket" info --format '{{json .SecurityOptions}}' | grep -F 'name=rootless'
test "$(stat -c %u "$socket")" = "$(id -u)"
cp /usr/bin/busybox "$work/busybox"
cat > "$work/Dockerfile" <<'EOF'
FROM scratch
COPY busybox /busybox
COPY busybox /bin/sh
USER 65534:65534
CMD ["/busybox", "sh", "-c", "echo localzet-rootless-ready; exec /busybox sleep 600"]
EOF
python3 - "$work" <<'PY'
import sys
from pathlib import Path
from localzet.containers import Engine
engine = Engine()
assert not engine.rootful
assert "name=rootless" in engine._run("info", "--format", "{{json .SecurityOptions}}")
assert engine.inventory() == ()
context = Path(sys.argv[1])
tag = "localzet-rootless-ci:fixture"
# Keep daemon state outside the build context.
fixture = context / "fixture"
fixture.mkdir()
for name in ("busybox", "Dockerfile"):
    (context / name).rename(fixture / name)
rows = engine.build_image(tag, (fixture / "Dockerfile").read_text(), fixture)
image = next(row["ID"] for row in rows if row["Repository"] + ":" + row["Tag"] == tag)
row = next(row for row in engine.create_container("localzet-rootless-ci", image) if row.name == "localzet-rootless-ci")
cid = row.id
def state(rows):
    return next(row.state for row in rows if row.id == cid)
assert state(engine.action("start", cid)) == "running"
assert "localzet-rootless-ready" in engine.logs(cid)[0]
assert engine.metrics(cid)["PIDs"]
assert state(engine.action("restart", cid)) == "running"
assert state(engine.action("stop", cid)) == "exited"
assert state(engine.inventory()) == "exited"
print("PASS: actual rootless Docker build, lifecycle, logs and metrics")
PY

# Keep the stopped fixture for the real GTK lifecycle test. Preserve the
# user bus and runtime directory used by the rootless daemon.
GDK_BACKEND=x11 GSK_RENDERER=cairo GTK_A11Y=none xvfb-run -a -s '-screen 0 1440x900x24' \\
    /usr/bin/python3 scripts/ci/containers-rootless-gtk.py "$out"
/usr/bin/docker --host "unix://$socket" container rm localzet-rootless-ci
