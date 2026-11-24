"""User-scoped Aurora appearance changes with an explicit restore point."""
from __future__ import annotations

import ast
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Protocol


ROOT = Path(__file__).resolve().parents[3]
STATE_NAME = "appearance.json"
THEMES = {"blue", "purple", "black"}
EXTENSION_SCHEMA = "com.localzet.shell"
INTERFACE_SCHEMA = "org.gnome.desktop.interface"
BACKGROUND_SCHEMA = "org.gnome.desktop.background"
LOCAL_SCHEMA = "com.localzet.settings"
LOCAL_APPEARANCE_KEY = "appearance"
SAFE_KEYS = {
    (EXTENSION_SCHEMA, "appearance"),
    (INTERFACE_SCHEMA, "icon-theme"),
    (INTERFACE_SCHEMA, "color-scheme"),
    (BACKGROUND_SCHEMA, "picture-uri"),
    (BACKGROUND_SCHEMA, "picture-uri-dark"),
    (LOCAL_SCHEMA, LOCAL_APPEARANCE_KEY),
}


class AppearanceError(RuntimeError):
    """An appearance change could not be completed safely."""


class SettingsStore(Protocol):
    def supports(self, schema: str, key: str) -> bool: ...

    def get(self, schema: str, key: str) -> str: ...

    def set(self, schema: str, key: str, value: str) -> None: ...


@dataclass(frozen=True)
class SettingValue:
    schema: str
    key: str
    value: str


@dataclass(frozen=True)
class RestoreResult:
    restored: int
    pending: int


class GSettingsStore:
    def __init__(self) -> None:
        self._schemas: set[str] | None = None
        self._keys: dict[str, set[str]] = {}

    def _run(self, *args: str) -> str:
        try:
            completed = subprocess.run(
                ["gsettings", *args],
                check=True,
                capture_output=True,
                text=True,
                timeout=4,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise AppearanceError(f"gsettings недоступен: {error}") from error
        return completed.stdout.strip()

    def supports(self, schema: str, key: str) -> bool:
        if self._schemas is None:
            self._schemas = set(self._run("list-schemas").splitlines())
        if schema not in self._schemas:
            return False
        if schema not in self._keys:
            self._keys[schema] = set(self._run("list-keys", schema).splitlines())
        return key in self._keys[schema]

    def get(self, schema: str, key: str) -> str:
        raw = self._run("get", schema, key)
        try:
            value = ast.literal_eval(raw)
        except (SyntaxError, ValueError) as error:
            raise AppearanceError(f"Не удалось прочитать настройку {schema} {key}") from error
        if not isinstance(value, str):
            raise AppearanceError(f"Настройка {schema} {key} имеет неожиданный тип")
        return value

    def set(self, schema: str, key: str, value: str) -> None:
        self._run("set", schema, key, json.dumps(value))


def state_path() -> Path:
    state_home = os.environ.get("XDG_STATE_HOME")
    base = Path(state_home) if state_home else Path.home() / ".local/state"
    if not base.is_absolute():
        raise AppearanceError("XDG_STATE_HOME должен быть абсолютным путём")
    return base / "localzet" / STATE_NAME


def _local_appearance_path() -> Path:
    return state_path().with_name("appearance-current.json")


def _read_local_appearance() -> str | None:
    try:
        path = _local_appearance_path()
        if path.is_symlink() or not path.is_file():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (AppearanceError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or set(value) != {LOCAL_APPEARANCE_KEY}:
        return None
    theme = value[LOCAL_APPEARANCE_KEY]
    if not isinstance(theme, str) or theme not in THEMES:
        return None
    return theme


def _write_local_appearance(theme: str) -> None:
    if theme not in THEMES:
        raise AppearanceError("Неизвестная тема Aurora")
    path = _local_appearance_path()
    if path.is_symlink():
        raise AppearanceError("Файл текущей темы не должен быть символической ссылкой")
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".appearance-current-", dir=path.parent)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump({LOCAL_APPEARANCE_KEY: theme}, stream)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except BaseException:
            try:
                os.close(descriptor)
            except OSError:
                pass
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
    except OSError as error:
        raise AppearanceError("Не удалось сохранить выбранную тему") from error


def _icon_theme_available() -> bool:
    candidates = (
        Path("/usr/share/icons/Localzet/index.theme"),
        ROOT / "theme/icons/Localzet/index.theme",
    )
    return any(path.is_file() for path in candidates)


def _wallpaper_uri(theme: str) -> str:
    filename = f"aurora-{theme}.webp"
    candidates = (
        Path("/usr/share/backgrounds/localzet") / filename,
        ROOT / "assets/wallpapers" / filename,
    )
    for path in candidates:
        if path.is_file():
            return path.resolve().as_uri()
    raise AppearanceError("Не найден файл выбранных обоев Aurora")


def _changes(theme: str) -> list[SettingValue]:
    wallpaper = _wallpaper_uri(theme)
    return [
        SettingValue(INTERFACE_SCHEMA, "color-scheme", "prefer-dark"),
        SettingValue(INTERFACE_SCHEMA, "icon-theme", "Localzet"),
        SettingValue(BACKGROUND_SCHEMA, "picture-uri", wallpaper),
        SettingValue(BACKGROUND_SCHEMA, "picture-uri-dark", wallpaper),
        SettingValue(EXTENSION_SCHEMA, "appearance", theme),
    ]


def _write_snapshot(path: Path, values: list[SettingValue]) -> None:
    if path.is_symlink():
        raise AppearanceError("Файл восстановления не должен быть символической ссылкой")
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        data = [{"schema": item.schema, "key": item.key, "value": item.value} for item in values]
        descriptor, temporary = tempfile.mkstemp(prefix=".appearance-", dir=path.parent)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
    except OSError as error:
        raise AppearanceError("Не удалось сохранить файл восстановления") from error


def _read_snapshot(path: Path) -> list[SettingValue]:
    if path.is_symlink() or not path.is_file():
        raise AppearanceError("Файл восстановления отсутствует или имеет неверный тип")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AppearanceError("Файл восстановления повреждён") from error
    if not isinstance(raw, list) or not raw:
        raise AppearanceError("Файл восстановления повреждён")
    values: list[SettingValue] = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"schema", "key", "value"}:
            raise AppearanceError("Файл восстановления содержит неизвестные настройки")
        schema = item["schema"]
        key = item["key"]
        value = item["value"]
        if not all(isinstance(part, str) for part in (schema, key, value)):
            raise AppearanceError("Файл восстановления содержит неизвестные настройки")
        if (schema, key) not in SAFE_KEYS:
            raise AppearanceError("Файл восстановления содержит неизвестные настройки")
        if ((schema, key) == (LOCAL_SCHEMA, LOCAL_APPEARANCE_KEY)
                and value not in THEMES):
            raise AppearanceError("Файл восстановления содержит неизвестную тему")
        values.append(SettingValue(schema, key, value))
    return values


def apply_appearance(
    theme: str,
    *,
    store: SettingsStore | None = None,
    snapshot: Path | None = None,
) -> tuple[str, ...]:
    if theme not in THEMES:
        raise AppearanceError("Неизвестная тема Aurora")
    if not _icon_theme_available():
        raise AppearanceError("Тема значков Localzet не установлена")

    settings = store or GSettingsStore()
    target = snapshot or state_path()
    changes = [item for item in _changes(theme) if settings.supports(item.schema, item.key)]
    required = {
        (INTERFACE_SCHEMA, "icon-theme"),
        (BACKGROUND_SCHEMA, "picture-uri"),
    }
    available = {(item.schema, item.key) for item in changes}
    if not required.issubset(available):
        raise AppearanceError("Настройки значков или обоев GNOME недоступны")

    original = [SettingValue(item.schema, item.key, settings.get(item.schema, item.key)) for item in changes]
    original.append(SettingValue(
        LOCAL_SCHEMA,
        LOCAL_APPEARANCE_KEY,
        current_appearance(settings),
    ))
    if not target.exists():
        _write_snapshot(target, original)
    else:
        saved = _read_snapshot(target)
        saved_keys = {(item.schema, item.key) for item in saved}
        newly_available = [
            item for item in original if (item.schema, item.key) not in saved_keys
        ]
        if newly_available:
            _write_snapshot(target, saved + newly_available)

    applied: list[SettingValue] = []
    try:
        for item in changes:
            settings.set(item.schema, item.key, item.value)
            applied.append(item)
        _write_local_appearance(theme)
    except Exception as error:
        rollback_errors = []
        before = {(item.schema, item.key): item.value for item in original}
        for item in reversed(applied):
            try:
                settings.set(item.schema, item.key, before[(item.schema, item.key)])
            except Exception as rollback_error:
                rollback_errors.append(str(rollback_error))
        detail = f"; восстановление: {'; '.join(rollback_errors)}" if rollback_errors else ""
        raise AppearanceError(f"Не удалось применить тему: {error}{detail}") from error
    return tuple(f"{item.schema} {item.key}" for item in changes)


def restore_appearance(
    *,
    store: SettingsStore | None = None,
    snapshot: Path | None = None,
) -> RestoreResult:
    target = snapshot or state_path()
    if target.is_symlink():
        raise AppearanceError("Файл восстановления не должен быть символической ссылкой")
    if not target.is_file():
        raise AppearanceError("Исходные настройки ещё не сохранялись")
    values = _read_snapshot(target)
    has_local_appearance = any(
        (item.schema, item.key) == (LOCAL_SCHEMA, LOCAL_APPEARANCE_KEY)
        for item in values
    )
    if not has_local_appearance:
        extension_value = next(
            (item.value for item in values
             if (item.schema, item.key) == (EXTENSION_SCHEMA, "appearance")),
            "blue",
        )
        values.append(SettingValue(
            LOCAL_SCHEMA,
            LOCAL_APPEARANCE_KEY,
            extension_value if extension_value in THEMES else "blue",
        ))
    settings = store or GSettingsStore()
    unavailable = [
        item for item in values
        if (item.schema, item.key) != (LOCAL_SCHEMA, LOCAL_APPEARANCE_KEY)
        and not settings.supports(item.schema, item.key)
    ]
    pending = [
        item for item in unavailable
        if (item.schema, item.key) == (EXTENSION_SCHEMA, "appearance")
    ]
    missing = [item for item in unavailable if item not in pending]
    if missing:
        names = ", ".join(f"{item.schema} {item.key}" for item in missing)
        raise AppearanceError(f"Некоторые исходные настройки недоступны: {names}")
    available = [item for item in values if item not in pending]
    current = [
        SettingValue(
            item.schema,
            item.key,
            (_read_local_appearance() or current_appearance(settings))
            if (item.schema, item.key) == (LOCAL_SCHEMA, LOCAL_APPEARANCE_KEY)
            else settings.get(item.schema, item.key),
        )
        for item in available
    ]
    restored: list[SettingValue] = []
    try:
        for item in available:
            if (item.schema, item.key) == (LOCAL_SCHEMA, LOCAL_APPEARANCE_KEY):
                _write_local_appearance(item.value)
            else:
                settings.set(item.schema, item.key, item.value)
            restored.append(item)
    except Exception as error:
        before = {(item.schema, item.key): item.value for item in current}
        rollback_errors = []
        for item in reversed(restored):
            try:
                if (item.schema, item.key) == (LOCAL_SCHEMA, LOCAL_APPEARANCE_KEY):
                    _write_local_appearance(before[(item.schema, item.key)])
                else:
                    settings.set(item.schema, item.key, before[(item.schema, item.key)])
            except Exception as rollback_error:
                rollback_errors.append(str(rollback_error))
        detail = f"; возврат к текущим значениям: {'; '.join(rollback_errors)}" if rollback_errors else ""
        raise AppearanceError(f"Не удалось восстановить исходный вид: {error}{detail}") from error
    try:
        if pending:
            _write_snapshot(target, pending)
        else:
            target.unlink()
    except OSError as error:
        raise AppearanceError(
            "Настройки восстановлены, но не удалось обновить файл восстановления"
        ) from error
    except AppearanceError as error:
        raise AppearanceError(
            "Настройки восстановлены, но не удалось обновить файл восстановления"
        ) from error
    restored_settings = sum(
        (item.schema, item.key) != (LOCAL_SCHEMA, LOCAL_APPEARANCE_KEY)
        for item in restored
    )
    return RestoreResult(restored=restored_settings, pending=len(pending))


def current_appearance(store: SettingsStore | None = None) -> str:
    settings = store or GSettingsStore()
    try:
        if settings.supports(EXTENSION_SCHEMA, "appearance"):
            value = settings.get(EXTENSION_SCHEMA, "appearance")
            if value in THEMES:
                return value
    except AppearanceError:
        pass
    return _read_local_appearance() or "blue"
