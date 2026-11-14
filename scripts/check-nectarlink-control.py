#!/usr/bin/env python3
"""Check exact approved maintainer scripts before installing in disposable CI."""
from pathlib import Path
import subprocess
import sys
import tempfile

EXPECTED = b"""#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
exit 0
"""


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: check-nectarlink-control.py VERIFIED.deb")
    package = Path(sys.argv[1]).resolve(strict=True)
    with tempfile.TemporaryDirectory() as directory:
        control = Path(directory) / "control"
        subprocess.run(["dpkg-deb", "--control", str(package), str(control)], check=True)
        expected_files = {"control", "postinst", "postrm", "md5sums"}
        actual = {p.name for p in control.iterdir()}
        if actual - expected_files or not {"control", "postinst", "postrm"} <= actual:
            raise SystemExit(f"Unexpected maintainer control files: {sorted(actual)}")
        for name in ("postinst", "postrm"):
            path = control / name
            if path.is_symlink() or path.read_bytes() != EXPECTED:
                raise SystemExit(f"Unreviewed maintainer script: {name}")
    print("PASS: only the reviewed desktop/icon cache maintainer scripts")


if __name__ == "__main__":
    main()
