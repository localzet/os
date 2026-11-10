"""Strict, read-only feature catalogue and deterministic dependency planner.

No package operations, shell execution, network access or privilege escalation.
This planner is NOT a replacement for an authorized system package service.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib

ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
PACKAGE_RE = re.compile(r"^[a-z0-9][a-z0-9+.-]{0,127}$")
ALLOWED_STATUS = {"planned", "prototype", "supported"}
ALLOWED_KEYS = {"id", "title", "description", "status", "packages", "depends_on"}


class ManifestError(ValueError):
    """A feature manifest is invalid or cannot be resolved."""


@dataclass(frozen=True)
class Module:
    id: str
    title: str
    description: str
    status: str
    packages: tuple[str, ...]
    depends_on: tuple[str, ...]


def _strings(value: object, field: str, regex: re.Pattern[str]) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(x, str) and regex.fullmatch(x) for x in value):
        raise ManifestError(f"{field} must be a list of valid identifiers")
    if len(value) != len(set(value)):
        raise ManifestError(f"{field} contains duplicates")
    return tuple(value)


def load_catalog(directory: Path) -> dict[str, Module]:
    if not directory.is_dir():
        raise ManifestError(f"manifest directory not found: {directory}")
    modules: dict[str, Module] = {}
    for file in sorted(directory.glob("*.toml")):
        with file.open("rb") as stream:
            try:
                data = tomllib.load(stream)
            except tomllib.TOMLDecodeError as error:
                raise ManifestError(f"{file.name}: {error}") from error
        if not isinstance(data, dict) or set(data) != ALLOWED_KEYS:
            raise ManifestError(f"{file.name}: expected exactly {sorted(ALLOWED_KEYS)}")
        id_ = data["id"]
        if not isinstance(id_, str) or not ID_RE.fullmatch(id_) or file.stem != id_:
            raise ManifestError(f"{file.name}: invalid id or filename mismatch")
        if id_ in modules:
            raise ManifestError(f"duplicate module: {id_}")
        if not all(isinstance(data[k], str) and data[k].strip() for k in ("title", "description")):
            raise ManifestError(f"{id_}: title and description must be non-empty strings")
        if not isinstance(data["status"], str) or data["status"] not in ALLOWED_STATUS:
            raise ManifestError(f"{id_}: status must be one of {sorted(ALLOWED_STATUS)}")
        packages = _strings(data["packages"], f"{id_}.packages", PACKAGE_RE)
        deps = _strings(data["depends_on"], f"{id_}.depends_on", ID_RE)
        if id_ in deps:
            raise ManifestError(f"{id_}: module cannot depend on itself")
        modules[id_] = Module(id_, data["title"], data["description"], data["status"], packages, deps)
    if not modules:
        raise ManifestError("no module manifests found")
    # Validate the whole catalog, not only the modules requested by the user.
    resolve(modules, tuple(modules))
    return modules


def resolve(catalog: dict[str, Module], selected: tuple[str, ...]) -> tuple[Module, ...]:
    ordered: list[Module] = []
    state: dict[str, int] = {}

    def visit(id_: str) -> None:
        if id_ not in catalog:
            raise ManifestError(f"unknown module/dependency: {id_}")
        if state.get(id_) == 1:
            raise ManifestError(f"dependency cycle at {id_}")
        if state.get(id_) == 2:
            return
        state[id_] = 1
        for dependency in catalog[id_].depends_on:
            visit(dependency)
        state[id_] = 2
        ordered.append(catalog[id_])

    for id_ in selected:
        visit(id_)
    return tuple(ordered)
