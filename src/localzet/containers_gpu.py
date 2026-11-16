"""Local NVIDIA Docker diagnostics and explicit offline visibility probe."""
import json
import re
from localzet.hardware import inventory
from localzet.hardware_cuda import running_gpus
from localzet.containers import EngineError


def runtime_names(output):
    try:
        data = json.loads(output)
        if not isinstance(data, dict):
            raise ValueError("Invalid runtimes")
        return tuple(sorted(data))
    except (ValueError, TypeError) as error:
        raise EngineError("Docker runtime inventory unavailable") from error


def gpu_status(engine):
    if not engine.rootful:
        return {"state": "rootless-not-reviewed", "devices": []}
    try:
        gpus = running_gpus(inventory())
    except (OSError, ValueError):
        return {"state": "host-driver-unavailable", "devices": []}
    devices = [row.address for row in gpus]
    if "nvidia" not in runtime_names(engine._run("info", "--format", "{{json .Runtimes}}")):
        return {"state": "runtime-not-configured", "devices": devices}
    return {"state": "runtime-configured-unverified", "devices": devices}


def probe_gpu(engine, image_id):
    if not isinstance(image_id, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise EngineError("Select an explicitly trusted local CUDA image by full ID")
    status = gpu_status(engine)
    if status["state"] != "runtime-configured-unverified":
        raise EngineError("NVIDIA runtime is not ready on this local engine")
    if not any(row["ID"] == image_id for row in engine.resources("images")):
        raise EngineError("Selected image no longer exists")
    output = engine._run("container", "run", "--rm", "--pull", "never",
        "--runtime", "nvidia", "--gpus", "all", "--network", "none",
        "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--user", "65534:65534", "--pids-limit", "128", "--memory", "512m",
        "--env", "NVIDIA_DRIVER_CAPABILITIES=compute,utility",
        "--entrypoint", "nvidia-smi", image_id,
        "--query-gpu=pci.bus_id", "--format=csv,noheader", timeout=60)
    observed = []
    for line in output.splitlines():
        value = line.strip().lower()
        if not re.fullmatch(r"(?:0000)?[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]", value):
            raise EngineError("Unexpected container GPU output")
        observed.append(value[-12:])
    if len(observed) != len(set(observed)) or set(observed) != set(status["devices"]):
        raise EngineError("Container GPU inventory does not match host")
    return {"state": "gpu-visible", "devices": sorted(observed)}
