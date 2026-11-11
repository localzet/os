"""Temporary Live-only GDM 50.1 seat recovery; NEVER for installed systems.

Only returns to an existing user session after GDM shows an unexpected
greeter. Does not authenticate, spawn sessions or modify disk state.
"""
from __future__ import annotations
from pathlib import Path
import subprocess
import time

POLL_SECONDS = 5
MAX_POLLS = 90


def candidate_session(sessions: dict[str, dict[str, str]], active_id: str) -> str | None:
    active = sessions.get(active_id)
    if not active or active.get("Name") != "gdm-greeter" or active.get("Class") != "greeter":
        return None
    candidates = [
        sid for sid, info in sessions.items()
        if info.get("Name") == "localzet"
        and info.get("Class") == "user"
        and info.get("Seat") == "seat0"
        and info.get("Type") == "wayland"
        and info.get("Service") == "gdm-autologin"
        and info.get("State") in ("active", "online")
    ]
    return candidates[0] if len(candidates) == 1 else None


def _call(*argv: str) -> str:
    result = subprocess.run(argv, check=True, text=True,
                            capture_output=True, timeout=6)
    return result.stdout.strip()


def _props(*argv: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in _call(*argv).splitlines():
        key, delim, value = line.partition("=")
        if delim:
            out[key] = value
    return out


def collect() -> tuple[str, dict[str, dict[str, str]]]:
    active = _call("loginctl", "show-seat", "seat0", "-p", "ActiveSession", "--value")
    sessions: dict[str, dict[str, str]] = {}
    for line in _call("loginctl", "list-sessions", "--no-legend", "--no-pager").splitlines():
        fields = line.split()
        if fields and fields[0].replace("-", "").isalnum():
            sid = fields[0]
            sessions[sid] = _props("loginctl", "show-session", sid)
    return active, sessions


def may_recover(activations: int, now: float, last_activation: float,
                cooldown: float = 25.0) -> bool:
    return activations < 4 and now - last_activation >= cooldown


def main() -> int:
    if "boot=casper" not in Path("/proc/cmdline").read_text().split():
        print("Seat guard: not a Live session; no action", flush=True)
        return 0
    # GDM 50.1 may reassert its greeter after an apparently successful
    # recovery. Observe for a bounded window instead of exiting at the
    # first activation. Rate-limit and cap interventions to avoid flapping.
    activations = 0
    last_activation = -30.0
    cooldown = 25.0
    for _ in range(MAX_POLLS):
        time.sleep(POLL_SECONDS)
        try:
            current, sessions = collect()
            target = candidate_session(sessions, current)
            now = time.monotonic()
            if target and may_recover(activations, now, last_activation, cooldown):
                if activations >= 4:
                    print("Seat guard: intervention limit reached", flush=True)
                    return 0
                _call("loginctl", "activate", target)
                activations += 1
                last_activation = now
                print(
                    f"Seat guard: restored existing Live session {target} "
                    f"(recovery {activations}/4)",
                    flush=True,
                )
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            print(f"Seat guard: query failed: {error}", flush=True)
    print(f"Seat guard: observation complete, {activations} recoveries", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
