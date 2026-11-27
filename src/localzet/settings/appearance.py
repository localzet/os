"""User-scoped Aurora appearance changes with an explicit restore point."""
from __future__ import annotations

import ast
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
from functools import wraps
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from typing import Callable, ParamSpec, Protocol, TypeVar
import uuid


ROOT = Path(__file__).resolve().parents[3]
STATE_NAME = "appearance.json"
THEMES = {"blue", "purple", "black"}
EXTENSION_SCHEMA = "com.localzet.shell"
INTERFACE_SCHEMA = "org.gnome.desktop.interface"
BACKGROUND_SCHEMA = "org.gnome.desktop.background"
LOCAL_SCHEMA = "com.localzet.settings"
LOCAL_APPEARANCE_KEY = "appearance"
PTYXIS_SCHEMA = "org.gnome.Ptyxis"
PTYXIS_PROFILE_SCHEMA = "org.gnome.Ptyxis.Profile"
P = ParamSpec("P")
R = TypeVar("R")
SAFE_KEYS = {
    (EXTENSION_SCHEMA, "appearance"),
    (INTERFACE_SCHEMA, "accent-color"),
    (INTERFACE_SCHEMA, "icon-theme"),
    (INTERFACE_SCHEMA, "gtk-theme"),
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


@contextmanager
def _appearance_lock(target: Path):
    try:
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        lock_path = target.with_name(f".{target.name}.lock")
        descriptor = os.open(
            lock_path,
            os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
        )
    except OSError as error:
        raise AppearanceError("Не удалось заблокировать изменение оформления") from error
    try:
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
                or metadata.st_nlink != 1):
            os.close(descriptor)
            raise AppearanceError("Файл блокировки Appearance имеет неверный тип или владельца")
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
    except OSError as error:
        os.close(descriptor)
        raise AppearanceError("Не удалось заблокировать изменение оформления") from error
    try:
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _serialize_appearance(function: Callable[P, R]) -> Callable[P, R]:
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        target = kwargs.get("snapshot") or state_path()
        with _appearance_lock(Path(target)):
            return function(*args, **kwargs)

    return wrapped


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
        schema_id = schema.partition(":")[0]
        if self._schemas is None:
            schemas = set(self._run("list-schemas").splitlines())
            try:
                schemas.update(self._run("list-relocatable-schemas").splitlines())
            except AppearanceError:
                pass
            self._schemas = schemas
        if schema_id not in self._schemas:
            return False
        if schema_id not in self._keys:
            self._keys[schema_id] = set(self._run("list-keys", schema_id).splitlines())
        return key in self._keys[schema_id]

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


def _gtk_theme_name(theme: str) -> str:
    return f"Localzet-Aurora-{theme.title()}"


def _gtk_theme_available(theme: str) -> bool:
    name = _gtk_theme_name(theme)
    candidates = (
        Path("/usr/share/themes") / name / "gtk-4.0/gtk.css",
        ROOT / "theme/gtk" / name / "gtk-4.0/gtk.css",
    )
    return any(path.is_file() for path in candidates)


def _changes(theme: str) -> list[SettingValue]:
    wallpaper = _wallpaper_uri(theme)
    accent = "blue" if theme == "blue" else "purple"
    return [
        SettingValue(INTERFACE_SCHEMA, "color-scheme", "prefer-dark"),
        SettingValue(INTERFACE_SCHEMA, "accent-color", accent),
        SettingValue(INTERFACE_SCHEMA, "icon-theme", "Localzet"),
        SettingValue(BACKGROUND_SCHEMA, "picture-uri", wallpaper),
        SettingValue(BACKGROUND_SCHEMA, "picture-uri-dark", wallpaper),
        SettingValue(EXTENSION_SCHEMA, "appearance", theme),
    ]


def _ptyxis_profile_schema(settings: SettingsStore) -> str | None:
    if not settings.supports(PTYXIS_SCHEMA, "default-profile-uuid"):
        return None
    raw_uuid = settings.get(PTYXIS_SCHEMA, "default-profile-uuid")
    try:
        parsed_uuid = uuid.UUID(raw_uuid)
    except (ValueError, AttributeError):
        return None
    if raw_uuid not in {str(parsed_uuid), parsed_uuid.hex}:
        return None
    return (
        f"{PTYXIS_PROFILE_SCHEMA}:/org/gnome/Ptyxis/Profiles/"
        f"{raw_uuid}/"
    )


def _ensure_ptyxis_palettes() -> None:
    sources = (
        Path("/usr/share/localzet/ptyxis-palettes"),
        ROOT / "assets/terminal-palettes",
    )
    source = next(
        (candidate for candidate in sources if all(
            (candidate / f"Aurora {theme.title()}.palette").is_file()
            for theme in THEMES
        )),
        None,
    )
    if source is None:
        raise AppearanceError("Не найдены цветовые палитры Aurora для Ptyxis")

    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home) if data_home else Path.home() / ".local/share"
    if not base.is_absolute():
        raise AppearanceError("XDG_DATA_HOME должен быть абсолютным путём")
    destination = base / "org.gnome.Ptyxis" / "palettes"
    try:
        destination.mkdir(mode=0o700, parents=True, exist_ok=True)
        for theme in THEMES:
            target = destination / f"Aurora {theme.title()}.palette"
            descriptor, temporary = tempfile.mkstemp(
                prefix=".localzet-palette-", dir=destination
            )
            try:
                os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write((source / f"Aurora {theme.title()}.palette").read_bytes())
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, target)
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
        raise AppearanceError("Не удалось установить палитры Aurora для Ptyxis") from error


def _is_safe_setting(schema: str, key: str) -> bool:
    if (schema, key) in SAFE_KEYS:
        return True
    prefix = f"{PTYXIS_PROFILE_SCHEMA}:/org/gnome/Ptyxis/Profiles/"
    if key != "palette" or not schema.startswith(prefix) or not schema.endswith("/"):
        return False
    raw_uuid = schema[len(prefix):-1]
    try:
        parsed_uuid = uuid.UUID(raw_uuid)
    except ValueError:
        return False
    return raw_uuid in {str(parsed_uuid), parsed_uuid.hex}


def _ptyxis_palette_setting(
    theme: str, settings: SettingsStore
) -> SettingValue | None:
    schema = _ptyxis_profile_schema(settings)
    if schema is None or not settings.supports(schema, "palette"):
        return None
    return SettingValue(schema, "palette", f"Aurora {theme.title()}")


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
        if not _is_safe_setting(schema, key):
            raise AppearanceError("Файл восстановления содержит неизвестные настройки")
        if ((schema, key) == (LOCAL_SCHEMA, LOCAL_APPEARANCE_KEY)
                and value not in THEMES):
            raise AppearanceError("Файл восстановления содержит неизвестную тему")
        values.append(SettingValue(schema, key, value))
    return values


@_serialize_appearance
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
    changes = _changes(theme)
    if (settings.supports(INTERFACE_SCHEMA, "gtk-theme")
            and _gtk_theme_available(theme)):
        changes.append(SettingValue(
            INTERFACE_SCHEMA, "gtk-theme", _gtk_theme_name(theme),
        ))
    if settings.supports(PTYXIS_SCHEMA, "default-profile-uuid"):
        _ensure_ptyxis_palettes()
        palette = _ptyxis_palette_setting(theme, settings)
        if palette is not None:
            changes.append(palette)
    changes = [item for item in changes if settings.supports(item.schema, item.key)]
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


@_serialize_appearance
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
