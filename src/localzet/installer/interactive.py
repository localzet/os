"""Localzet installer front-end policy, shared by GUI and root entrypoint.

The first physical-device candidate supports only a blank internal SSD and
UEFI without Secure Boot. Other internal disks must be disconnected. No
automatic selection, repartitioning, dual boot, or firmware NVRAM writes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

from localzet.installer.preflight import read_lsblk
from localzet.installer.target import identity, read_only_target_plan, revalidate_target

ENABLED = Path("/usr/lib/localzet/installer-enabled")
ENGINE = Path("/usr/lib/localzet/install-engine.sh")
USER = re.compile(r"[a-z][a-z0-9_-]{0,30}")
MAX_REQUEST = 16384


def command(*args: str) -> str:
    return subprocess.check_output(args, text=True, timeout=20).strip()


def live_source_disk() -> str | None:
    """Only a directly mounted optical/USB ISO is supported; no loop chains."""
    if command("findmnt", "-n", "-o", "FSTYPE", "--mountpoint", "/cdrom") != "iso9660":
        raise ValueError("Поддерживается только образ ISO, записанный напрямую на USB или DVD.")
    source = command("findmnt", "-n", "-o", "SOURCE", "--mountpoint", "/cdrom")
    if not source.startswith("/dev/"):
        raise ValueError("Не удалось определить загрузочный носитель.")
    nodes = [line.split(None, 1) for line in command(
        "lsblk", "-s", "-n", "-r", "-o", "TYPE,PATH", source
    ).splitlines()]
    disks = [path for kind, path in nodes if kind == "disk"]
    if len(disks) == 1:
        return disks[0]
    if not disks and any(kind == "rom" for kind, _ in nodes):
        return None
    raise ValueError("Не удалось однозначно определить диск загрузочного носителя.")


def eligible_plan(payload: dict, selected: str, live_disk: str | None) -> dict:
    plan = read_only_target_plan(payload, selected)
    disks = [d for d in payload["blockdevices"] if d.get("type") == "disk"]
    matches = [d for d in disks if identity(d) == selected]
    if len(matches) != 1:
        raise ValueError("Накопитель отсутствует или не уникален.")
    target = matches[0]
    if target.get("path") == live_disk:
        raise ValueError("Нельзя установить систему на загрузочный носитель.")
    if target.get("children") or target.get("pttype") or target.get("fstype"):
        raise ValueError("Первый выпуск поддерживает только пустой SSD без разделов и сигнатур.")
    if target.get("tran") not in ("nvme", "sata", "ata"):
        raise ValueError("Поддерживаются только внутренние NVMe/SATA SSD.")
    if any(d.get("path") not in (target.get("path"), live_disk) for d in disks):
        raise ValueError("Для первой версии отключите все остальные диски, кроме загрузочного носителя.")
    return plan


def confirmation_for(plan: dict) -> str:
    return "INSTALL " + plan["selected_identity"]


def validate_account(username: str, password: str) -> None:
    if not isinstance(username, str) or not USER.fullmatch(username) or username in ("root", "localzet"):
        raise ValueError("Имя пользователя: 1–31 символ, латиница в нижнем регистре, цифры, дефис или подчёркивание.")
    if (not isinstance(password, str) or not 10 <= len(password) <= 128
            or any(char in password for char in (":", "\n", "\r", "\x00"))):
        raise ValueError("Пароль должен содержать 10–128 символов; двоеточие и перенос строки запрещены.")


def validate_request(request: dict) -> None:
    if not isinstance(request, dict) or set(request) != {
        "plan", "confirmation", "backup_acknowledged", "username", "password"
    }:
        raise ValueError("Неверный запрос установки.")
    plan = request["plan"]
    if not isinstance(plan, dict) or plan.get("operation") != "read_only_target_plan":
        raise ValueError("Сначала проверьте целевой диск.")
    if not isinstance(plan.get("selected_identity"), str):
        raise ValueError("Не указан идентификатор накопителя.")
    if request["backup_acknowledged"] is not True or request["confirmation"] != confirmation_for(plan):
        raise ValueError("Не подтверждена установка на выбранный SSD.")
    validate_account(request["username"], request["password"])


def stable_device(path: str) -> Path:
    target = Path(path).resolve(strict=True)
    candidates = []
    for candidate in Path("/dev/disk/by-id").iterdir():
        if (candidate.is_symlink() and not re.search(r"-part[0-9]+$", candidate.name)
                and candidate.name.startswith(("wwn-", "nvme-eui.", "nvme-", "ata-", "scsi-"))):
            try:
                if candidate.resolve(strict=True) == target:
                    candidates.append(candidate)
            except OSError:
                continue
    if not candidates:
        raise ValueError("У накопителя нет стабильного идентификатора /dev/disk/by-id.")
    return sorted(candidates, key=lambda p: (not p.name.startswith(("wwn-", "nvme-eui.")), p.name))[0]


EFI_GUID = "8be4df61-93ca-11d2-aa0d-00e098032b8c"


def efi_flag(directory: Path, name: str) -> int | None:
    """efivarfs prepends four attribute bytes to firmware variable data."""
    path = directory / f"{name}-{EFI_GUID}"
    try:
        payload = path.read_bytes()[4:]
    except FileNotFoundError:
        return None
    if len(payload) not in (1, 2, 4):
        raise ValueError(f"Некорректная переменная UEFI {name}.")
    value = int.from_bytes(payload, "little")
    if value not in (0, 1):
        raise ValueError(f"Неизвестное значение UEFI {name}.")
    return value


def secure_boot_disabled(directory: Path) -> bool:
    secure = efi_flag(directory, "SecureBoot")
    setup = efi_flag(directory, "SetupMode")
    # Never treat an enabled or unreadable flag as disabled. Setup Mode
    # explicitly means no enrolled Platform Key and no enforced Secure Boot.
    if secure == 1:
        return False
    return secure == 0 or (secure is None and setup == 1)


def check_environment() -> None:
    if not ENABLED.is_file() or not ENGINE.is_file():
        raise ValueError("Установщик не включён в этот образ.")
    cmdline = Path("/proc/cmdline").read_text().split()
    if "boot=casper" not in cmdline or "localzet.install-test=1" in cmdline:
        raise ValueError("Установка доступна только в интерактивном Live-образе.")
    if command("findmnt", "-n", "-o", "FSTYPE", "/") != "overlay":
        raise ValueError("Не обнаружена Live-файловая система.")
    efi = Path("/sys/firmware/efi/efivars")
    if not efi.is_dir() or command("findmnt", "-n", "-o", "FSTYPE", "--mountpoint", str(efi)) != "efivarfs":
        raise ValueError("Не удалось прочитать переменные UEFI (efivarfs).")
    if not secure_boot_disabled(efi):
        raise ValueError("Требуется UEFI с выключенным Secure Boot.")
    if not Path("/cdrom/casper/filesystem.squashfs").is_file():
        raise ValueError("Не найден исходный образ системы.")


def backend() -> int:
    """Root-only fixed command, input via stdin, no arbitrary command/paths."""
    try:
        if os.geteuid() != 0:
            raise ValueError("Для установки необходимы административные права.")
        check_environment()
        data = sys.stdin.buffer.read(MAX_REQUEST + 1)
        if len(data) > MAX_REQUEST:
            raise ValueError("Запрос слишком большой.")
        request = json.loads(data)
        validate_request(request)
        previous = request["plan"]
        payload = read_lsblk()
        live_disk = live_source_disk()
        plan = eligible_plan(payload, previous["selected_identity"], live_disk)
        revalidate_target(payload, previous)
        device = stable_device(plan["current_device_path_unstable"])
        target = device.resolve(strict=True)
        info = target.stat()
        if not stat.S_ISBLK(info.st_mode):
            raise ValueError("Целевое устройство не является диском.")
        if command("wipefs", "--no-act", "--noheadings", "--output", "TYPE", str(device)):
            raise ValueError("На SSD обнаружены сигнатуры данных.")
        # Re-read after probing. The engine repeats device identity checks
        # before each write; this is not an atomic hotplug-safe device lock.
        fresh = read_lsblk()
        eligible_plan(fresh, previous["selected_identity"], live_disk)
        revalidate_target(fresh, previous)
        if device.resolve(strict=True) != target or target.stat().st_rdev != info.st_rdev:
            raise ValueError("Накопитель изменился после подтверждения.")
        devno = f"{os.major(info.st_rdev):x}:{os.minor(info.st_rdev):x}"
        password = request.pop("password")
        proc = subprocess.run(
            ["/usr/bin/unshare", "--mount", "--propagation", "private",
             "/bin/bash", str(ENGINE), "interactive", str(device),
             request["username"], str(target), devno],
            input=password + "\n", text=True,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C.UTF-8"},
        )
        return proc.returncode
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"Установка остановлена: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(backend())
