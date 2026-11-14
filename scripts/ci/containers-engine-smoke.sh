#!/usr/bin/env bash
# Real Docker lifecycle on isolated runner; no host mounts or exposed ports.
set -Eeuo pipefail
[[ ${LOCALZET_DISPOSABLE_VM:-} == 1 && $EUID != 0 ]]
export PYTHONPATH="$PWD/src"
out="$PWD/out/containers-engine"
mkdir -p "$out"
work="$(mktemp -d)"
name="localzet-ci-${GITHUB_RUN_ID:-$$}-${GITHUB_RUN_ATTEMPT:-1}"
image="$name:fixture"
# Never honor a remote Docker context in this test.
docker_local() { /usr/bin/docker --host unix:///var/run/docker.sock "$@"; }
cleanup() {
    docker_local rm -f "$name" >/dev/null 2>&1 || true
    docker_local image rm "$image" >/dev/null 2>&1 || true
    rm -rf -- "$work"
}
trap cleanup EXIT
docker_local version > "$out/engine.txt"
cp /usr/bin/busybox "$work/busybox"
cat > "$work/Dockerfile" <<'EOF'
FROM scratch
COPY busybox /busybox
USER 65534:65534
CMD ["/busybox", "sleep", "600"]
EOF
docker_local build --network none -t "$image" "$work"
cid="$(docker_local create --name "$name" --network none --read-only --cap-drop ALL --security-opt no-new-privileges "$image")"
python3 - "$cid" "$out" <<'PY'
import json, sys
from dataclasses import asdict
from pathlib import Path
from localzet.containers import Engine
cid, output = sys.argv[1], Path(sys.argv[2])
engine = Engine(rootful=True)
def verify(rows, expected, label):
    row = next(row for row in rows if row.id == cid)
    assert row.state == expected, row
    (output / f"{label}.json").write_text(json.dumps(asdict(row), indent=2))
    print("PASS:", label, row.state)
verify(engine.inventory(), "created", "inventory")
verify(engine.action("start", cid), "running", "start")
verify(engine.action("restart", cid), "running", "restart")
verify(engine.action("stop", cid), "exited", "stop")
PY
