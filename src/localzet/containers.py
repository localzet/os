"""Localzet Containers: local Docker Engine adapter, no privilege escalation.

Default is the user's rootless socket. Rootful access requires an explicit
choice and pre-existing permission; Docker access is effectively root access.
No remote contexts, arbitrary commands, credential inspection or auto-install.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import stat
import subprocess

DOCKER = Path("/usr/bin/docker")
ID = re.compile(r"[0-9a-f]{64}")
ACTIONS = frozenset(("start", "stop", "restart"))


class EngineError(RuntimeError):
    pass


@dataclass(frozen=True)
class Container:
    id: str
    name: str
    image: str
    state: str
    status: str
    ports: str


def parse_inventory(output: str) -> tuple[Container, ...]:
    rows = []
    seen = set()
    for line in output.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            values = [row[k] for k in ("ID", "Names", "Image", "State", "Status", "Ports")]
        except (ValueError, TypeError, KeyError) as exc:
            raise EngineError("Docker returned an invalid inventory") from exc
        if not all(isinstance(v, str) for v in values) or not ID.fullmatch(values[0]) or values[0] in seen:
            raise EngineError("Docker returned invalid or duplicate container IDs")
        seen.add(values[0])
        rows.append(Container(*values))
    return tuple(rows)


class Engine:
    def __init__(self, *, rootful: bool = False):
        if os.geteuid() == 0:
            raise EngineError("Do not run Localzet Containers as root")
        if type(rootful) is not bool:
            raise EngineError("Explicit engine choice required")
        self.rootful = rootful
        self.socket = Path("/var/run/docker.sock" if rootful else f"/run/user/{os.getuid()}/docker.sock")

    def _check(self):
        if not DOCKER.is_file() or not os.access(DOCKER, os.X_OK):
            raise EngineError("Docker CLI is not installed")
        try:
            info = self.socket.stat()
        except OSError as exc:
            raise EngineError("Selected local Docker socket is unavailable") from exc
        if not stat.S_ISSOCK(info.st_mode) or (not self.rootful and info.st_uid != os.getuid()):
            raise EngineError("Selected socket is not the expected Docker socket")
        if not os.access(self.socket, os.W_OK):
            raise EngineError("No permission to access selected Docker engine; no automatic elevation")

    def _run(self, *args: str) -> str:
        self._check()
        # A fixed local endpoint; ignore inherited Docker contexts, SSH, TLS,
        # config overrides and plugin PATH. No shell, sudo or pkexec.
        env = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "LC_ALL": "C.UTF-8"}
        try:
            proc = subprocess.run(
                [str(DOCKER), "--host", f"unix://{self.socket}", *args],
                text=True, capture_output=True, timeout=45, env=env, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            raise EngineError("Docker command could not complete; refresh to check actual state") from exc
        if proc.returncode:
            # Avoid returning arbitrary daemon errors that may contain secrets.
            raise EngineError(f"Docker command failed (exit {proc.returncode}); refresh engine state")
        return proc.stdout

    def inventory(self) -> tuple[Container, ...]:
        return parse_inventory(self._run("container", "ls", "--all", "--no-trunc", "--format", "{{json .}}"))

    def action(self, action: str, container_id: str) -> tuple[Container, ...]:
        if action not in ACTIONS or not isinstance(container_id, str) or not ID.fullmatch(container_id):
            raise EngineError("Invalid action or full container ID")
        # Resolve freshly before acting; never use an ambiguous name or prefix.
        if not any(row.id == container_id for row in self.inventory()):
            raise EngineError("Container no longer exists on the selected engine")
        args = ("--time", "10") if action in ("stop", "restart") else ()
        self._run("container", action, *args, container_id)
        return self.inventory()


def main() -> int:
    parser = argparse.ArgumentParser(description="Localzet Containers local engine")
    parser.add_argument("--rootful", action="store_true", help="Explicitly use privileged system Docker socket")
    parser.add_argument("action", choices=("list", "start", "stop", "restart"))
    parser.add_argument("container_id", nargs="?")
    args = parser.parse_args()
    if (args.action == "list") != (args.container_id is None):
        parser.error("Actions require exactly one full container ID")
    try:
        engine = Engine(rootful=args.rootful)
        rows = engine.inventory() if args.action == "list" else engine.action(args.action, args.container_id)
        print(json.dumps([asdict(row) for row in rows], ensure_ascii=False, indent=2))
    except EngineError as exc:
        parser.exit(2, f"{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
