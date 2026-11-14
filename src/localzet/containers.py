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
import selectors
import time
import stat
import subprocess

DOCKER = Path("/usr/bin/docker")
ID = re.compile(r"[0-9a-f]{64}")
LOG_LIMIT = 256 * 1024
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


@dataclass(frozen=True)
class Stack:
    name: str
    status: str
    config_files: str


def parse_stacks(output: str) -> tuple[Stack, ...]:
    try:
        data = json.loads(output)
        if not isinstance(data, list):
            raise ValueError("Expected project array")
        rows = []
        names = set()
        for item in data:
            values = [item[key] for key in ("Name", "Status", "ConfigFiles")]
            if (not all(isinstance(value, str) for value in values)
                    or not values[0] or values[0] in names):
                raise ValueError("Invalid or duplicate Compose project")
            names.add(values[0])
            rows.append(Stack(*values))
        return tuple(rows)
    except (ValueError, TypeError, KeyError) as exc:
        raise EngineError("Docker Compose returned an invalid project inventory") from exc


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

    def stacks(self) -> tuple[Stack, ...]:
        # List only. Config paths are reported as metadata, never opened or
        # passed back into Compose automatically; they can be untrusted labels.
        return parse_stacks(self._run("compose", "ls", "--all", "--format", "json"))

    def _lookup(self, container_id: str) -> Container:
        if not isinstance(container_id, str) or not ID.fullmatch(container_id):
            raise EngineError("Invalid full container ID")
        row = next((row for row in self.inventory() if row.id == container_id), None)
        if row is None:
            raise EngineError("Container no longer exists on the selected engine")
        return row

    def metrics(self, container_id: str) -> dict[str, str]:
        if self._lookup(container_id).state != "running":
            raise EngineError("Container is not running")
        output = self._run("container", "stats", "--no-stream", "--no-trunc",
                           "--format", "{{json .}}", container_id)
        try:
            row = json.loads(output)
            if row["ID"] != container_id:
                raise ValueError("Container ID mismatch")
            result = {key: row[key] for key in ("CPUPerc", "MemUsage", "NetIO", "BlockIO", "PIDs")}
            if not all(isinstance(value, str) for value in result.values()):
                raise ValueError("Invalid metric")
        except (ValueError, TypeError, KeyError) as exc:
            raise EngineError("Docker returned invalid metrics") from exc
        return result

    def logs(self, container_id: str) -> tuple[str, bool]:
        # Explicit snapshot only. Logs can contain secrets: never cache, upload
        # or put them into generic error messages. Bound both time and bytes.
        self._lookup(container_id)
        self._check()
        env = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "LC_ALL": "C.UTF-8"}
        deadline = time.monotonic() + 20
        data = bytearray()
        truncated = False
        try:
            with subprocess.Popen([str(DOCKER), "--host", f"unix://{self.socket}",
                    "container", "logs", "--tail", "100", "--timestamps", container_id],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env) as proc:
                try:
                    with selectors.DefaultSelector() as selector:
                        selector.register(proc.stdout, selectors.EVENT_READ)
                        while True:
                            remaining = deadline - time.monotonic()
                            if remaining <= 0 or not selector.select(remaining):
                                raise EngineError("Docker log snapshot timed out")
                            chunk = os.read(proc.stdout.fileno(), min(65536, LOG_LIMIT + 1 - len(data)))
                            if not chunk:
                                break
                            data.extend(chunk)
                            if len(data) > LOG_LIMIT:
                                truncated = True
                                del data[LOG_LIMIT:]
                                break
                    if not truncated and proc.wait(timeout=max(0.1, deadline - time.monotonic())):
                        raise EngineError("Docker log snapshot failed")
                finally:
                    if proc.poll() is None:
                        proc.kill()  # stops the CLI reader, not the container
                        proc.wait()
        except (OSError, subprocess.SubprocessError) as exc:
            raise EngineError("Docker log snapshot failed") from exc
        return data.decode("utf-8", errors="replace"), truncated

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
    parser.add_argument("action", choices=("list", "stacks", "start", "stop", "restart"))
    parser.add_argument("container_id", nargs="?")
    args = parser.parse_args()
    if (args.action in ("list", "stacks")) != (args.container_id is None):
        parser.error("Actions require exactly one full container ID")
    try:
        engine = Engine(rootful=args.rootful)
        rows = (engine.inventory() if args.action == "list" else engine.stacks() if args.action == "stacks"
                else engine.action(args.action, args.container_id))
        print(json.dumps([asdict(row) for row in rows], ensure_ascii=False, indent=2))
    except EngineError as exc:
        parser.exit(2, f"{exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
