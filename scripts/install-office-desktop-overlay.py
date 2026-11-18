#!/usr/bin/env python3
"""Shadow the vendor desktop ID in /usr/local, preserving MIME associations."""
from pathlib import Path
import argparse
import re
import subprocess

EXEC = re.compile(r'^(?P<key>Exec|TryExec)=(?P<program>"[^"]+"|[^\s]+)(?P<suffix>[ \t].*)?$')
VENDOR = {"desktopeditors", "onlyoffice-desktopeditors", "/usr/bin/desktopeditors",
          "/usr/bin/onlyoffice-desktopeditors", "/opt/onlyoffice/desktopeditors/DesktopEditors"}
LAUNCHER = "/usr/bin/localzet-office"


def transform(text: str) -> str:
    lines = []
    found = False
    group = ""
    for line in text.splitlines():
        if line.startswith("[") and line.endswith("]"):
            group = line
        if line.startswith(("Exec=", "TryExec=")):
            match = EXEC.fullmatch(line)
            if not match or match["program"].strip('"') not in VENDOR:
                raise ValueError("Unexpected vendor desktop command: " + line)
            if group == "[Desktop Entry]" and match["key"] == "Exec":
                found = True
            line = match["key"] + "=" + LAUNCHER + (match["suffix"] or "")
        elif line == "DBusActivatable=true":
            line = "DBusActivatable=false"
        lines.append(line)
    if not found:
        raise ValueError("Vendor desktop entry missing primary Exec")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    ns = parser.parse_args()
    root = ns.root.resolve(strict=True)
    if root == Path("/") or not (root / "var/lib/dpkg/status").is_file():
        raise ValueError("Disposable target only")
    manifest = subprocess.check_output(["chroot", str(root), "dpkg-query", "-L", "onlyoffice-desktopeditors"], text=True)
    entries = [Path(line) for line in manifest.splitlines()
               if line.startswith("/usr/share/applications/") and line.endswith(".desktop")]
    if not entries:
        raise ValueError("No vendor desktop entry found")
    target = root / "usr/local/share/applications"
    target.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        source = root / entry.relative_to("/")
        if source.parent != root / "usr/share/applications" or not source.is_file():
            raise ValueError("Unexpected desktop file path")
        destination = target / entry.name
        if destination.exists() or destination.is_symlink():
            raise ValueError("Refusing to replace an existing local override")
        destination.write_text(transform(source.read_text(encoding="utf-8")), encoding="utf-8")
        destination.chmod(0o644)
        print("Localzet Office launcher override:", entry.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
