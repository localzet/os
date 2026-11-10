"""Offline module planner CLI (read-only)."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .modules import ManifestError, load_catalog, resolve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Localzet OS feature catalogue (read-only prototype)")
    parser.add_argument("--manifest-dir", type=Path, default=Path(__file__).resolve().parents[2] / "config" / "modules")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="validate the whole manifest set")
    commands.add_parser("list", help="list optional system features")
    plan = commands.add_parser("plan", help="print dependency-ordered plan, never install")
    plan.add_argument("ids", nargs="+", help="module IDs")
    args = parser.parse_args(argv)
    try:
        catalog = load_catalog(args.manifest_dir)
        if args.command == "validate":
            print(f"OK: {len(catalog)} valid manifests")
        elif args.command == "list":
            for module in catalog.values():
                print(f"{module.id:15} {module.status:10} {module.title}")
        else:
            chosen = resolve(catalog, tuple(args.ids))
            print("READ-ONLY PLAN (no packages or services will be changed):")
            for module in chosen:
                print(f"- {module.id} [{module.status}] {module.title}")
                print(f"  apt candidates (not verified): {', '.join(module.packages) or '(none)'}")
            if any(m.status != "supported" for m in chosen):
                print("Not installable: at least one component is not marked supported.")
        return 0
    except (ManifestError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
