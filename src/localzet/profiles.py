"""Read-only profile selection, package origin separation, and review gates.

This is not a package manager. No network, installation or elevation.
Only explicit official-source provisioning after review may act on a plan.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

ID = re.compile(r"[a-z][a-z0-9-]{0,63}")
PACKAGE = re.compile(r"[a-z0-9][a-z0-9+.-]{0,127}")
PROFILES = ("minimal", "standard", "complete")
BROWSERS = ("chrome", "edge")


def _ids(values, allowed):
    if (not isinstance(values, list) or any(not isinstance(v, str) or v not in allowed for v in values)
            or len(values) != len(set(values))):
        raise ValueError("Invalid, duplicate or unknown selection")
    return values


def load_manifest(path: Path) -> dict:
    data = json.loads(path.read_text())
    if data.get("schema") != 1 or data.get("status") != "planning-only":
        raise ValueError("Unsupported profile manifest")
    apps = data["applications"]
    profiles = data["profiles"]
    if not isinstance(apps, dict) or set(profiles) != set(PROFILES):
        raise ValueError("Invalid profiles")
    for key, app in apps.items():
        if not ID.fullmatch(key) or set(app) != {"title", "source", "packages", "url", "review"}:
            raise ValueError("Invalid application record")
        if app["source"] not in ("ubuntu", "upstream", "localzet") or app["review"] != "pending":
            raise ValueError("Unknown source or unreviewed manifest version")
        if not isinstance(app["title"], str) or not app["title"]:
            raise ValueError("Invalid title")
        url = urlsplit(app["url"])
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("Invalid source reference")
        packages = app["packages"]
        if not isinstance(packages, list) or any(not isinstance(p, str) or not PACKAGE.fullmatch(p) for p in packages) or len(packages) != len(set(packages)):
            raise ValueError("Invalid package names")
        if app["source"] == "ubuntu" and (not packages or url.hostname != "archive.ubuntu.com"):
            raise ValueError("Ubuntu packages must use the Ubuntu archive")
    for profile in profiles.values():
        if set(profile) != {"required", "optional", "browser_choice"} or type(profile["browser_choice"]) is not bool:
            raise ValueError("Invalid profile fields")
        required = _ids(profile["required"], apps)
        optional = _ids(profile["optional"], apps)
        if set(required) & set(optional) or set(BROWSERS) & set(required + optional):
            raise ValueError("Conflicting choices")
    if not set(profiles["minimal"]["required"]) <= set(profiles["standard"]["required"]) <= set(profiles["complete"]["required"]):
        raise ValueError("Profiles must preserve core capabilities")
    for name in ("standard", "complete"):
        if not {"office", "telegram"} <= set(profiles[name]["required"]):
            raise ValueError("Office and Telegram are required")
    return data


def plan(data: dict, profile: str, *, browser: str | None = None, extras=()) -> dict:
    if profile not in PROFILES:
        raise ValueError("Unknown profile")
    spec = data["profiles"][profile]
    extras = _ids(list(extras), spec["optional"])
    if browser is not None and browser not in BROWSERS:
        raise ValueError("Select Chrome or Edge, not both")
    chosen = spec["required"] + extras + ([browser] if browser else [])
    records = [{"id": key, **data["applications"][key]} for key in chosen]
    ubuntu = sorted({p for app in records if app["source"] == "ubuntu" for p in app["packages"]})
    return {"operation": "read_only_profile_plan", "profile": profile,
            "applications": records, "ubuntu_package_candidates": ubuntu,
            "external_or_localzet_pending": [app["id"] for app in records if app["source"] != "ubuntu"],
            "browser_choice_pending": spec["browser_choice"] and browser is None,
            "install_ready": False, "write_operations_available": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("profile", choices=PROFILES)
    parser.add_argument("--browser", choices=BROWSERS)
    parser.add_argument("--extra", action="append", default=[])
    args = parser.parse_args()
    try:
        result = plan(load_manifest(args.manifest), args.profile, browser=args.browser, extras=args.extra)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"Profile rejected: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
