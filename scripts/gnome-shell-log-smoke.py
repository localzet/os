#!/usr/bin/env python3
"""Report JavaScript errors from the current disposable GNOME session."""
import subprocess


def emit(line: str) -> None:
    print(line, flush=True)


def main() -> int:
    try:
        result = subprocess.run(
            ["journalctl", "--user", "-b", "--no-pager", "--output=cat"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as error:
        emit(f"LOCALZET_SHELL_LOG_RESULT FAIL journal-unavailable: {error}")
        return 1

    errors = [line for line in result.stdout.splitlines() if "JS ERROR:" in line]
    for line in errors:
        emit(f"LOCALZET_SHELL_JS_ERROR {line}")
    status = "FAIL" if errors else "PASS"
    emit(f"LOCALZET_SHELL_LOG_RESULT {status} js_errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
