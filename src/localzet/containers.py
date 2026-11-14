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


# Fixed field allowlist: never expose labels, mounts, environment or credentials.
RESOURCE_FIELDS = {
    "images": ("Repository", "Tag", "ID", "Size"),
    "volumes": ("Name", "Driver", "Scope"),
    "networks": ("Name", "ID", "Driver", "Scope"),
}
RESOURCE_COMMANDS = {
    "images": ("image", "ls", "--all", "--no-trunc"),
    "volumes": ("volume", "ls"),
    "networks": ("network", "ls", "--no-trunc"),
}


def parse_resources(kind: str, output: str) -> tuple[dict[str, str], ...]:
    if kind not in RESOURCE_FIELDS:
        raise EngineError("Unknown resource kind")
    rows = []
    try:
        for line in output.splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            row = {key: item[key] for key in RESOURCE_FIELDS[kind]}
            if not all(isinstance(value, str) for value in row.values()):
                raise ValueError("Invalid resource field")
            if kind == "images" and not re.fullmatch(r"sha256:[0-9a-f]{64}", row["ID"]):
                raise ValueError("Invalid image ID")
            if kind == "networks" and not ID.fullmatch(row["ID"]):
                raise ValueError("Invalid network ID")
            rows.append(row)
    except (ValueError, TypeError, KeyError) as exc:
        raise EngineError("Docker returned an invalid resource inventory") from exc
    return tuple(rows)


@dataclass(frozen=True)
class Deployment:
    network: str = "none"
    ports: tuple[str, ...] = ()
    environment: tuple[str, ...] = ()
    mounts: tuple[str, ...] = ()
    memory_mib: int = 512
    cpus: str = ""
    restart: str = "no"


def deployment_args(options: Deployment) -> tuple[str, ...]:
    if not isinstance(options, Deployment):
        raise EngineError("Invalid deployment profile")
    if options.network not in ("none", "bridge") and not ID.fullmatch(options.network):
        raise EngineError("Select none, bridge or a full local network ID")
    if type(options.memory_mib) is not int or not 64 <= options.memory_mib <= 65536:
        raise EngineError("Memory must be 64–65536 MiB")
    if options.cpus and not re.fullmatch(r"(?:0\.[1-9]|[1-9][0-9]?(?:\.[0-9])?)", options.cpus):
        raise EngineError("CPU limit must be 0.1–99.9")
    if options.restart not in ("no", "on-failure", "unless-stopped", "always"):
        raise EngineError("Invalid restart policy")
    args = ["--network", options.network, "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--user", "65534:65534",
            "--pids-limit", "256", "--memory", f"{options.memory_mib}m"]
    if options.cpus:
        args += ["--cpus", options.cpus]
    if options.restart != "no":
        args += ["--restart", options.restart]
    if len(options.ports) > 32 or len(options.environment) > 64 or len(options.mounts) > 16:
        raise EngineError("Too many deployment parameters")
    if options.ports and options.network == "none":
        raise EngineError("Port mappings require a network")
    bindings = set()
    for value in options.ports:
        match = re.fullmatch(r"([0-9]{1,5}):([0-9]{1,5})/(tcp|udp)", value)
        if not match or not all(1 <= int(x) <= 65535 for x in match.groups()[:2]):
            raise EngineError("Ports must be HOST:CONTAINER/tcp or /udp")
        host, target, protocol = match.groups()
        key = (int(host), protocol)
        if key in bindings:
            raise EngineError("Duplicate host port")
        bindings.add(key)
        args += ["--publish", f"127.0.0.1:{int(host)}:{int(target)}/{protocol}"]
    keys = set()
    for value in options.environment:
        key, sep, data = value.partition("=")
        if not sep or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) or key in keys or len(data) > 4096 or any(x in data for x in ("\x00", "\n", "\r")):
            raise EngineError("Invalid or duplicate environment variable")
        keys.add(key)
        args += ["--env", value]
    targets = set()
    for value in options.mounts:
        match = re.fullmatch(r"([a-zA-Z0-9][a-zA-Z0-9_.-]{1,62}):(/data(?:/[a-zA-Z0-9_-]+)*):(ro|rw)", value)
        if not match:
            raise EngineError("Mount must be NAME:/data[/subdir]:ro or :rw")
        name, target, mode = match.groups()
        if any(target == old or target.startswith(old + "/") or old.startswith(target + "/") for old in targets):
            raise EngineError("Overlapping mount targets")
        targets.add(target)
        args += ["--mount", f"type=volume,source={name},target={target},volume-nocopy" + (",readonly" if mode == "ro" else "")]
    return tuple(args)


def compose_document(source: str) -> tuple[str, tuple[str, ...]]:
    """Strict JSON subset of YAML; generate a new restricted Compose document."""
    if not isinstance(source, str) or len(source.encode("utf-8")) > 65536:
        raise EngineError("Compose document exceeds 64 KiB")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate key")
            result[key] = value
        return result
    try:
        data = json.loads(source, object_pairs_hook=unique)
        if not isinstance(data, dict) or set(data) != {"services"}:
            raise ValueError("Only services are accepted")
        services = data["services"]
        if not isinstance(services, dict) or not 1 <= len(services) <= 16:
            raise ValueError("Expected 1–16 services")
        result = {}
        for name, service in services.items():
            if not re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", name):
                raise ValueError("Invalid service name")
            if not isinstance(service, dict) or set(service) != {"image"}:
                raise ValueError("Only image is accepted per service")
            image = service["image"]
            if not isinstance(image, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
                raise ValueError("Full local image ID required")
            result[name] = {"image": image, "pull_policy": "never", "network_mode": "none",
                            "read_only": True, "cap_drop": ["ALL"], "user": "65534:65534",
                            "security_opt": ["no-new-privileges:true"], "mem_limit": "512m",
                            "pids_limit": 256}
        return json.dumps({"services": result}, indent=2), tuple(result)
    except (ValueError, TypeError, RecursionError) as exc:
        raise EngineError("Invalid Compose JSON: use unique service names and full local image IDs only") from exc


class StudioStore:
    """Private, content-addressed storage of validated Studio source."""
    def __init__(self, root: Path | None = None):
        self.root = root if root is not None else Path.home() / ".local/share/localzet/compose"

    def _directory(self):
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise EngineError("Studio directory must be private and owned by the current user")

    @staticmethod
    def identity(source: str) -> str:
        import hashlib
        document, _ = compose_document(source)
        return hashlib.sha256(document.encode("utf-8")).hexdigest()

    def save(self, source: str) -> str:
        import tempfile
        identity = self.identity(source)
        self._directory()
        target = self.root / (identity + ".json")
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.root, delete=False) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(source)
                stream.flush()
                os.fsync(stream.fileno())
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        return identity

    def load(self, identity: str) -> str:
        if not isinstance(identity, str) or not ID.fullmatch(identity):
            raise EngineError("Invalid Studio project ID")
        self._directory()
        fd = os.open(self.root / (identity + ".json"), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise EngineError("Invalid Studio project file")
            data = stream.read(65537)
        if len(data) > 65536:
            raise EngineError("Studio project exceeds size limit")
        source = data.decode("utf-8")
        if self.identity(source) != identity:
            raise EngineError("Studio project fingerprint mismatch")
        return source

    def projects(self) -> tuple[str, ...]:
        self._directory()
        return tuple(sorted(path.stem for path in self.root.glob("*.json")
                            if ID.fullmatch(path.stem)))


@dataclass(frozen=True)
class MetricSample:
    cpu: float
    memory: float


def metric_sample(values: dict[str, str]) -> MetricSample:
    import math
    def percent(value):
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?%", value):
            raise EngineError("Invalid percentage")
        result = float(value[:-1])
        if not math.isfinite(result):
            raise EngineError("Invalid percentage")
        return result
    cpu = percent(values["CPUPerc"])
    memory = percent(values["MemPerc"])
    if memory > 100:
        raise EngineError("Invalid memory percentage")
    return MetricSample(cpu, memory)


def build_argument_flags(values: tuple[str, ...]) -> tuple[str, ...]:
    if len(values) > 32:
        raise EngineError("Too many build arguments")
    result = []
    seen = set()
    for value in values:
        key, sep, data = value.partition("=")
        if not sep or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) or key in seen or len(data) > 4096 or any(ch in data for ch in ("\x00", "\n", "\r")):
            raise EngineError("Invalid or duplicate build argument")
        seen.add(key)
        result.extend(("--build-arg", value))
    return tuple(result)


def read_build_tail(proc, timeout: int) -> str:
    deadline = time.monotonic() + timeout
    tail = bytearray()
    truncated = False
    with selectors.DefaultSelector() as selector:
        selector.register(proc.stdout, selectors.EVENT_READ)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not selector.select(remaining):
                raise EngineError("Build output timed out; inspect Docker state")
            chunk = os.read(proc.stdout.fileno(), 65536)
            if not chunk:
                break
            tail.extend(chunk)
            if len(tail) > LOG_LIMIT:
                del tail[:-LOG_LIMIT]
                truncated = True
    return ("[Earlier output omitted]\n" if truncated else "") + tail.decode("utf-8", errors="replace")


def validate_registry_tag(reference: str, *, qualified: bool = False) -> None:
    pattern = r"(?:[a-z0-9][a-z0-9.-]*(?::[0-9]{1,5})?/)?(?:[a-z0-9]+(?:[._-][a-z0-9]+)*/)*[a-z0-9]+(?:[._-][a-z0-9]+)*:[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}"
    if not isinstance(reference, str) or len(reference) > 255 or not re.fullmatch(pattern, reference):
        raise EngineError("Explicit repository and tag required")
    host, slash, path = reference.partition("/")
    if qualified and (not slash or not ("." in host or ":" in host or host == "localhost") or "/" not in path and host == "docker.io"):
        raise EngineError("Explicit registry host and repository required")


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

    def _run(self, *args: str, timeout: int = 45) -> str:
        self._check()
        # A fixed local endpoint; ignore inherited Docker contexts, SSH, TLS,
        # config overrides and plugin PATH. No shell, sudo or pkexec.
        env = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "LC_ALL": "C.UTF-8"}
        try:
            proc = subprocess.run(
                [str(DOCKER), "--host", f"unix://{self.socket}", *args],
                text=True, capture_output=True, timeout=timeout, env=env, check=False)
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

    def resources(self, kind: str) -> tuple[dict[str, str], ...]:
        if kind not in RESOURCE_COMMANDS:
            raise EngineError("Unknown resource kind")
        return parse_resources(kind, self._run(*RESOURCE_COMMANDS[kind], "--format", "{{json .}}"))

    def create_resource(self, kind: str, name: str) -> tuple[dict[str, str], ...]:
        if kind not in ("volumes", "networks") or not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{1,62}", name):
            raise EngineError("Invalid resource kind or name (2–63 ASCII characters)")
        if any(row["Name"] == name for row in self.resources(kind)):
            raise EngineError("Resource already exists")
        if kind == "volumes":
            self._run("volume", "create", "--driver", "local", name)
        else:
            self._run("network", "create", "--driver", "bridge", "--internal", name)
        return self.resources(kind)

    def remove_resource(self, kind: str, identity: str) -> tuple[dict[str, str], ...]:
        # No volume deletion, force, prune or name-based removal.
        if kind not in ("images", "networks") or not isinstance(identity, str):
            raise EngineError("Unsupported resource removal")
        pattern = r"sha256:[0-9a-f]{64}" if kind == "images" else r"[0-9a-f]{64}"
        if not re.fullmatch(pattern, identity):
            raise EngineError("Full resource ID required")
        rows = [row for row in self.resources(kind) if row["ID"] == identity]
        if not rows:
            raise EngineError("Resource no longer exists")
        if kind == "networks" and any(row["Name"] in ("bridge", "host", "none") or row["Scope"] != "local" for row in rows):
            raise EngineError("Built-in and non-local networks cannot be removed")
        if kind == "images" and len(rows) != 1:
            raise EngineError("Image has multiple references; explicit tag management required")
        if kind == "images":
            self._run("image", "rm", "--no-prune", identity)
        else:
            self._run("network", "rm", identity)
        return self.resources(kind)

    def tag_image(self, image_id: str, reference: str) -> tuple[dict[str, str], ...]:
        validate_registry_tag(reference)
        rows = self.resources("images")
        if not isinstance(image_id, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise EngineError("Full local image ID required")
        if not any(row["ID"] == image_id for row in rows):
            raise EngineError("Image no longer exists")
        if any(row["Repository"] + ":" + row["Tag"] == reference for row in rows):
            raise EngineError("Destination tag already exists")
        self._run("image", "tag", image_id, reference)
        return self.resources("images")

    def push_image(self, image_id: str, reference: str) -> tuple[dict[str, str], ...]:
        # Explicit fully qualified registry + repository + tag. No credentials
        # passed by this application; Docker uses its existing credential store.
        validate_registry_tag(reference, qualified=True)
        if not isinstance(image_id, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise EngineError("Full local image ID required")
        rows = self.resources("images")
        if not any(row["ID"] == image_id and row["Repository"] + ":" + row["Tag"] == reference for row in rows):
            raise EngineError("Selected image tag changed or no longer exists")
        self._run("image", "push", reference, timeout=600)
        return self.resources("images")

    def pull_image(self, reference: str) -> tuple[dict[str, str], ...]:
        # Explicit tag or digest; no URL, credentials, flags or implicit latest.
        pattern = r"(?:[a-z0-9][a-z0-9.-]*(?::[0-9]{1,5})?/)?(?:[a-z0-9]+(?:[._-][a-z0-9]+)*/)*[a-z0-9]+(?:[._-][a-z0-9]+)*(?::[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}|@sha256:[0-9a-f]{64})"
        if not isinstance(reference, str) or len(reference) > 255 or not re.fullmatch(pattern, reference):
            raise EngineError("Explicit image tag or SHA-256 digest required")
        self._run("image", "pull", reference, timeout=600)
        return self.resources("images")

    def build_image(self, tag: str, dockerfile: str, context: Path, *, build_args: tuple[str, ...] = (), output=None) -> tuple[dict[str, str], ...]:
        # Trusted, explicitly selected context only. Pass the reviewed Dockerfile
        # via stdin, not a path that could change between review and execution.
        if not isinstance(tag, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,62}:[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}", tag):
            raise EngineError("Use a local image name and explicit tag")
        if not isinstance(dockerfile, str) or not dockerfile.strip() or len(dockerfile.encode("utf-8")) > 65536 or "\x00" in dockerfile:
            raise EngineError("Dockerfile must be 1–65536 bytes")
        if not isinstance(context, Path) or not context.is_absolute() or not context.is_dir():
            raise EngineError("Select an existing absolute build context")
        context = context.resolve()
        if context in (Path("/"), Path.home().resolve()):
            raise EngineError("Select a specific project directory, not home or root")
        if any(row["Repository"] + ":" + row["Tag"] == tag for row in self.resources("images")):
            raise EngineError("Tag already exists; choose a new tag")
        args = build_argument_flags(build_args)
        self._check()
        env = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "LC_ALL": "C.UTF-8"}
        import tempfile
        # Drain the pipe continuously, retaining only the last 256 KiB.
        with tempfile.TemporaryFile() as source:
            source.write(dockerfile.encode("utf-8"))
            source.seek(0)
            try:
                with subprocess.Popen([str(DOCKER), "--host", f"unix://{self.socket}",
                        "build", "--network", "none", "--pull=false", "--progress", "plain",
                        "--tag", tag, *args, "--file", "-", str(context)], stdin=source,
                        stdout=subprocess.PIPE if output is not None else subprocess.DEVNULL,
                        stderr=subprocess.STDOUT if output is not None else subprocess.DEVNULL, env=env) as proc:
                    try:
                        if output is not None:
                            tail = read_build_tail(proc, 600)
                            output(tail)
                        if proc.wait(timeout=600 if output is None else 5):
                            raise EngineError("Image build failed; inspect Docker state")
                    finally:
                        if proc.poll() is None:
                            proc.kill()
                            proc.wait()
            except (OSError, subprocess.SubprocessError) as exc:
                raise EngineError("Image build could not complete; inspect Docker state") from exc
        rows = self.resources("images")
        if not any(row["Repository"] + ":" + row["Tag"] == tag for row in rows):
            raise EngineError("Build finished but target tag was not found")
        return rows

    def image_history(self, image_id: str) -> tuple[dict[str, str], ...]:
        if not isinstance(image_id, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise EngineError("Full local image ID required")
        if not any(row["ID"] == image_id for row in self.resources("images")):
            raise EngineError("Image no longer exists")
        raw = self._run("image", "history", "--no-trunc", "--format", "{{json .}}", image_id)
        rows = []
        try:
            for line in raw.splitlines()[:256]:
                item = json.loads(line)
                row = {key: item[key] for key in ("ID", "CreatedSince", "Size")}
                if not all(isinstance(value, str) for value in row.values()):
                    raise ValueError("Invalid history")
                rows.append(row)
        except (ValueError, TypeError, KeyError) as exc:
            raise EngineError("Invalid image history") from exc
        return tuple(rows)

    def create_container(self, name: str, image_id: str, options: Deployment = Deployment()) -> tuple[Container, ...]:
        if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{1,62}", name):
            raise EngineError("Invalid container name (2–63 ASCII characters)")
        if not isinstance(image_id, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise EngineError("Full local image ID required")
        args = deployment_args(options)
        if not any(row["ID"] == image_id for row in self.resources("images")):
            raise EngineError("Image no longer exists")
        if any(row.name == name for row in self.inventory()):
            raise EngineError("Container already exists")
        if options.network not in ("none", "bridge"):
            if not any(row["ID"] == options.network and row["Driver"] == "bridge" and row["Scope"] == "local" for row in self.resources("networks")):
                raise EngineError("Select an existing local bridge network")
        if options.mounts:
            volumes = {row["Name"] for row in self.resources("volumes") if row["Driver"] == "local" and row["Scope"] == "local"}
            for mount in options.mounts:
                name_of_volume = mount.split(":", 1)[0]
                if name_of_volume not in volumes:
                    raise EngineError("Select an existing local volume")
                # Local driver options can hide host bind mounts or remote storage.
                raw = self._run("volume", "inspect", "--format", "{{json .Options}}", name_of_volume)
                try:
                    if json.loads(raw) not in (None, {}):
                        raise ValueError("Non-default volume options")
                except ValueError as exc:
                    raise EngineError("Only default local volumes are supported") from exc
        self._run("container", "create", "--name", name, "--pull", "never", *args, image_id)
        return self.inventory()

    def validate_compose(self, source: str) -> str:
        document, names = compose_document(source)
        # Private temporary directory; no external config, interpolation, includes
        # or file paths from the editor are passed to Compose.
        import tempfile
        with tempfile.TemporaryDirectory(prefix="localzet-compose-") as directory:
            path = Path(directory) / "compose.json"
            path.write_text(document, encoding="utf-8")
            self._run("compose", "--project-directory", directory, "--env-file", "/dev/null",
                      "-p", "localzet-validation", "-f", str(path), "config", "--quiet")
        return document

    def studio_status(self, source: str) -> tuple[Container, ...]:
        identity = StudioStore.identity(source)
        project = "localzet-studio-" + identity[:32]
        rows = parse_inventory(self._run("container", "ls", "--all", "--no-trunc",
            "--filter", f"label=com.docker.compose.project={project}",
            "--filter", f"label=com.localzet.studio.document={identity}",
            "--format", "{{json .}}"))
        return rows

    def managed_compose(self, source: str, action: str) -> str:
        """Operate only on a deterministic, app-owned restricted project."""
        import hashlib
        import tempfile
        document, _ = compose_document(source)
        digest = hashlib.sha256(document.encode("utf-8")).hexdigest()
        project = "localzet-studio-" + digest[:32]
        if action not in ("up", "start", "stop", "restart", "down"):
            raise EngineError("Unsupported Compose action")
        if action == "up":
            images = {row["ID"] for row in self.resources("images")}
            if any(service["image"] not in images for service in json.loads(document)["services"].values()):
                raise EngineError("A selected local image is missing")
        # Compose project names are not an authorization boundary. Refuse any
        # existing project unless every container carries our exact document
        # fingerprint and service label. No foreign stack adoption.
        def verify():
            output = self._run("container", "ls", "--all", "--no-trunc",
                "--filter", f"label=com.docker.compose.project={project}",
                "--format", "{{json .ID}}")
            ids = []
            for line in output.splitlines():
                try:
                    cid = json.loads(line)
                    if not isinstance(cid, str) or not ID.fullmatch(cid):
                        raise ValueError("Invalid ID")
                except (ValueError, TypeError) as exc:
                    raise EngineError("Invalid project inventory") from exc
                ids.append(cid)
            for cid in ids:
                raw = self._run("container", "inspect", "--format",
                    '{{json .Config.Labels}}', cid)
                try:
                    labels = json.loads(raw)
                    if (labels.get("com.localzet.studio.document") != digest or
                        labels.get("com.docker.compose.project") != project or
                        labels.get("com.docker.compose.service") not in json.loads(document)["services"]):
                        raise ValueError("Foreign project")
                except (ValueError, TypeError, AttributeError) as exc:
                    raise EngineError("Project identity mismatch; no changes made") from exc
            return ids
        existing = verify()
        if action != "up" and not existing:
            raise EngineError("No matching managed project exists")
        model = json.loads(document)
        for service in model["services"].values():
            service["labels"] = {"com.localzet.studio.document": digest}
        with tempfile.TemporaryDirectory(prefix="localzet-compose-") as directory:
            path = Path(directory) / "compose.json"
            path.write_text(json.dumps(model), encoding="utf-8")
            args = ("compose", "--project-directory", directory, "--env-file",
                    "/dev/null", "-p", project, "-f", str(path))
            self._run(*args, "config", "--quiet")
            current = verify()
            if action != "up":
                if not current:
                    raise EngineError("Managed project disappeared; refresh")
                # Target exact verified IDs; never expand to other project labels.
                for cid in current:
                    if action == "down":
                        self._run("container", "stop", "--time", "10", cid)
                        self._run("container", "rm", cid)
                    else:
                        self._run("container", action, cid)
                return project
            if current:
                raise EngineError("Project already exists; use Start or Down")
            self._run(*args, "up", "-d", "--no-build", "--pull", "never", "--no-recreate", timeout=120)
        return project

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
            result = {key: row[key] for key in ("CPUPerc", "MemUsage", "NetIO", "BlockIO", "PIDs", "MemPerc")}
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
