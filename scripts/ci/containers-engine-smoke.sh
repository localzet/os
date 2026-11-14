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
    if [[ -f "$work/compose.yaml" ]]; then
        docker_local compose -p "$name" -f "$work/compose.yaml" down >/dev/null 2>&1 || true
    fi
    docker_local rm -f "$name" >/dev/null 2>&1 || true
    docker_local volume rm "$name" >/dev/null 2>&1 || true
    docker_local network rm "$name" >/dev/null 2>&1 || true
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
CMD ["/busybox", "sh", "-c", "echo localzet-fixture-ready; exec /busybox sleep 600"]
EOF
docker_local build --network none -t "$image" "$work"
docker_local compose version > "$out/compose-version.txt"
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
metrics = engine.metrics(cid)
assert all(metrics[key] for key in ("CPUPerc", "MemUsage", "PIDs")), metrics
(output / "metrics.json").write_text(json.dumps(metrics, indent=2))
print("PASS: real container metrics")
logs, truncated = engine.logs(cid)
assert "localzet-fixture-ready" in logs and not truncated
# Only the original CI fixture message, never an arbitrary user's logs.
print("PASS: original fixture log snapshot")
verify(engine.action("restart", cid), "running", "restart")
verify(engine.action("stop", cid), "exited", "stop")
PY
# Start an isolated Compose stack using only the locally built image.
cat > "$work/compose.yaml" <<EOF
services:
  fixture:
    image: $image
    pull_policy: never
    network_mode: none
    read_only: true
    cap_drop: [ALL]
    security_opt: [no-new-privileges:true]
EOF
docker_local compose -p "$name" -f "$work/compose.yaml" up -d --no-build --pull never
python3 - "$name" "$out" <<'PY'
import json, sys
from dataclasses import asdict
from pathlib import Path
from localzet.containers import Engine
stack = next(row for row in Engine(rootful=True).stacks() if row.name == sys.argv[1])
assert "running" in stack.status, stack
(Path(sys.argv[2]) / "compose.json").write_text(json.dumps(asdict(stack), indent=2))
print("PASS: real Compose project inventory")
PY

# Real resource inventory; create only isolated, uniquely named fixtures.
docker_local volume create "$name" >/dev/null
docker_local network create --internal "$name" >/dev/null
python3 - "$name" "$image" "$out" <<'PY'
import json, sys
from pathlib import Path
from localzet.containers import Engine
name, image, out = sys.argv[1:]
engine = Engine(rootful=True)
for kind, predicate in (
    ("images", lambda row: row["Repository"] + ":" + row["Tag"] == image),
    ("volumes", lambda row: row["Name"] == name),
    ("networks", lambda row: row["Name"] == name),
):
    row = next(row for row in engine.resources(kind) if predicate(row))
    (Path(out) / f"{kind}.json").write_text(json.dumps(row, indent=2))
    print("PASS: real", kind, "inventory")
PY
