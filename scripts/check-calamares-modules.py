#!/usr/bin/env python3
"""Check staged Calamares sequence against actual packaged module descriptors.
No installer code is imported or executed. Requires PyYAML.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

import yaml

REPO = Path(__file__).resolve().parents[1]
MODULE = re.compile(r"[a-z][a-z0-9-]*")


def check(root: Path, settings: Path) -> dict:
    config = yaml.safe_load(settings.read_text())
    sequence = config["sequence"]
    required = set()
    for section in sequence:
        if not isinstance(section, dict) or len(section) != 1:
            raise ValueError("invalid sequence entry")
        kind, modules = next(iter(section.items()))
        if kind not in ("show", "exec") or not isinstance(modules, list):
            raise ValueError("invalid module sequence")
        for module in modules:
            if not isinstance(module, str) or not MODULE.fullmatch(module):
                raise ValueError("unsupported module reference")
            required.add(module)
    available = set()
    for descriptor in root.glob("usr/lib/*/calamares/modules/*/module.desc"):
        if descriptor.is_file():
            available.add(descriptor.parent.name)
    for descriptor in root.glob("usr/lib/calamares/modules/*/module.desc"):
        if descriptor.is_file():
            available.add(descriptor.parent.name)
    return {
        "required": sorted(required),
        "available": sorted(available),
        "missing": sorted(required - available),
        "installer_executed": False,
        "physical_disks_accessed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extracted_package", type=Path)
    parser.add_argument("--settings", type=Path, default=REPO / "packaging/calamares/staging/settings.conf.example")
    args = parser.parse_args()
    if not args.extracted_package.is_dir() or args.extracted_package.resolve() == Path("/"):
        parser.error("provide an extracted package directory, not the host root")
    try:
        result = check(args.extracted_package, args.settings)
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        print(f"Module contract invalid: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 1 if result["missing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
