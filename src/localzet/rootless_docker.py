"""Manage only Localzet's explicitly started user Docker service."""
from __future__ import annotations

import json
import os
from pathlib import Path
import pwd
import stat
import subprocess

from localzet.containers import Engine, EngineError

UNIT = "localzet-rootless-docker.service"
FRAGMENT = "/usr/lib/systemd/user/" + UNIT
SYSTEMCTL = "/usr/bin/systemctl"
REQUIRED = ("/usr/bin/rootlesskit", "/usr/bin/newuidmap", "/usr/bin/newgidmap",
            "/usr/bin/slirp4netns", "/usr/bin/containerd", "/usr/sbin/sysctl", "/usr/share/docker.io/contrib/dockerd-rootless.sh")


def has_range(text: str, username: str, uid: int) -> bool:
    for line in text.splitlines():
        fields = line.split(":")
        if len(fields) != 3 or fields[0] not in (username, str(uid)):
            continue
        try:
            start, count = map(int, fields[1:])
        except ValueError:
            continue
        if start > 0 and count >= 65536 and start + count <= 2**32 - 1:
            return True
    return False


def _env():
    uid = os.getuid()
    return {"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "LC_ALL": "C.UTF-8",
            "XDG_RUNTIME_DIR": f"/run/user/{uid}",
            "DBUS_SESSION_BUS_ADDRESS": f"unix:path=/run/user/{uid}/bus"}


def _ctl(*args):
    try:
        result = subprocess.run([SYSTEMCTL, "--user", "--no-pager", *args], env=_env(),
                                text=True, capture_output=True, timeout=145)
    except (OSError, subprocess.SubprocessError) as exc:
        raise EngineError("Пользовательская служба недоступна; проверьте состояние Docker") from exc
    if result.returncode:
        raise EngineError("Не удалось управлять пользовательской службой Docker. Проверьте journalctl --user -u " + UNIT)
    return result.stdout.strip()


def _preflight():
    if os.geteuid() == 0:
        raise EngineError("Rootless Docker запускается только обычным пользователем")
    if "boot=casper" in Path("/proc/cmdline").read_text().split():
        raise EngineError("Сначала установите Localzet OS")
    if not Path(FRAGMENT).is_file():
        raise EngineError("Компонент управляемого Docker не установлен")
    runtime = Path(f"/run/user/{os.getuid()}")
    info = runtime.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise EngineError("Некорректный каталог пользовательского сеанса")
    _ctl("daemon-reload")
    if _ctl("show", UNIT, "--property=FragmentPath", "--value") != FRAGMENT:
        raise EngineError("Обнаружено переопределение службы Docker; автоматическая настройка запрещена")
    if _ctl("show", UNIT, "--property=DropInPaths", "--value"):
        raise EngineError("Обнаружены пользовательские изменения службы Docker")
    return runtime / "docker.sock"


def start_unit(socket: Path) -> None:
    """Retry once only after a failed, fully stopped managed service.

    On slow cold boots dockerd can time out waiting for its own containerd.
    Do not remove sockets, reset foreign units or start a privileged daemon.
    """
    try:
        _ctl("start", UNIT)
    except EngineError:
        if (_ctl("show", UNIT, "--property=ActiveState", "--value") != "failed"
                or _ctl("show", UNIT, "--property=MainPID", "--value") != "0"
                or socket.exists() or socket.is_symlink()):
            raise
        _ctl("reset-failed", UNIT)
        _ctl("start", UNIT)


def change(action: str) -> str:
    if action not in ("start", "stop"):
        raise ValueError("Unknown rootless action")
    socket = _preflight()
    if action == "stop":
        _ctl("stop", UNIT)
        return "остановлен"
    if any(not Path(path).is_file() or not os.access(path, os.X_OK) for path in REQUIRED):
        raise EngineError("Не установлены компоненты rootless Docker")
    uid = os.getuid()
    username = pwd.getpwuid(uid).pw_name
    if not all(has_range(Path("/etc/" + name).read_text(), username, uid) for name in ("subuid", "subgid")):
        raise EngineError("Для rootless Docker нужны диапазоны subuid и subgid не менее 65536")
    if _ctl("show", "docker.service", "--property=LoadState", "--value") != "not-found":
        raise EngineError("Обнаружена другая пользовательская служба Docker; выберите существующий движок")
    active = _ctl("show", UNIT, "--property=ActiveState", "--value") == "active"
    if (socket.exists() or socket.is_symlink()) and not active:
        raise EngineError("Сокет Docker уже существует; чужой движок не будет остановлен или заменён")
    start_unit(socket)
    engine = Engine()
    try:
        options = json.loads(engine._run("info", "--format", "{{json .SecurityOptions}}", timeout=30))
        if not isinstance(options, list) or "name=rootless" not in options:
            raise EngineError("Движок не подтвердил rootless-режим")
    except (EngineError, ValueError, OSError):
        # Do not claim success or stop a potentially existing engine.
        raise EngineError("Служба запущена, но rootless-режим не подтверждён. Проверьте журнал.")
    return "rootless подтверждён"
