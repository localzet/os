"""Unprivileged CUDA compiler and actual GPU compute acceptance probe."""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import tempfile

from localzet.hardware import inventory
from localzet.hardware_cuda import running_gpus, TOOLKITS


SOURCE = r"""
#include <cstdio>
#include <cuda_runtime.h>

__global__ void fixture(int *value) { *value = 42; }

#define CHECK(call) do { if ((call) != cudaSuccess) return 2; } while (0)

int main() {
    int count = 0;
    CHECK(cudaGetDeviceCount(&count));
    if (count < 1 || count > 64) return 3;
    for (int i = 0; i < count; ++i) {
        CHECK(cudaSetDevice(i));
        char bus[32] = {};
        CHECK(cudaDeviceGetPCIBusId(bus, sizeof(bus), i));
        int *device = nullptr;
        int host = 0;
        CHECK(cudaMalloc(&device, sizeof(int)));
        fixture<<<1, 1>>>(device);
        CHECK(cudaGetLastError());
        CHECK(cudaDeviceSynchronize());
        CHECK(cudaMemcpy(&host, device, sizeof(int), cudaMemcpyDeviceToHost));
        CHECK(cudaFree(device));
        if (host != 42) return 4;
        std::printf("PASS %s %d\n", bus, host);
    }
    return 0;
}
"""


def compiler(env):
    for path in ("/usr/bin/nvcc", "/usr/lib/nvidia-cuda-toolkit/bin/nvcc",
                 "/usr/local/cuda-13.1/bin/nvcc", "/usr/lib/cuda-13.1/bin/nvcc"):
        if not Path(path).is_file() or not os.access(path, os.X_OK):
            continue
        output = subprocess.run([path, "--version"], capture_output=True, text=True,
                                check=True, timeout=15, env=env).stdout
        match = re.search(r"release (12\.4|13\.1),", output)
        if match:
            return path, match.group(1)
    raise ValueError("No reviewed CUDA 12.4 or 13.1 compiler found")


def parse_results(output, addresses):
    actual = set()
    for line in output.splitlines():
        match = re.fullmatch(r"PASS ([0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]) 42", line)
        if not match or match.group(1).lower() in actual:
            raise ValueError("Unexpected or duplicate CUDA compute result")
        actual.add(match.group(1).lower())
    if actual != set(addresses):
        raise ValueError("CUDA compute did not succeed on every detected NVIDIA GPU")
    return sorted(actual)


def verify():
    if os.geteuid() == 0:
        raise ValueError("CUDA compute verification must run as the desktop user, not root")
    gpus = running_gpus(inventory())
    if len(gpus) > 64:
        raise ValueError("Too many GPUs for the bounded probe")
    env = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "LC_ALL": "C.UTF-8"}
    nvcc, release = compiler(env)
    _, _, minimum, supported = next(row for row in TOOLKITS if row[1] == release)
    if not all(gpu.capability in supported and tuple(map(int, gpu.driver_version.split("."))) >= minimum
               for gpu in gpus):
        raise ValueError("Installed compiler is incompatible with the verified runtime")
    targets = sorted({gpu.capability.replace(".", "") for gpu in gpus})
    with tempfile.TemporaryDirectory(prefix="localzet-cuda-probe-") as directory:
        source = Path(directory) / "probe.cu"
        executable = Path(directory) / "probe"
        source.write_text(SOURCE, encoding="utf-8")
        argv = [nvcc, str(source), "-o", str(executable)]
        for target in targets:
            argv.extend(("-gencode", f"arch=compute_{target},code=sm_{target}"))
        subprocess.run(argv, cwd=directory, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       env=env, check=True, timeout=180)
        result = subprocess.run([str(executable)], cwd=directory, capture_output=True, text=True,
                                env=env, check=True, timeout=60)
        devices = parse_results(result.stdout, [gpu.address for gpu in gpus])
    return {"status": "compute-verified", "toolkit": release, "compiler": nvcc,
            "devices": devices, "kernel_result": 42}
