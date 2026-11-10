"""Unit tests for the ISO verification protocol (mocked xorriso output).

These tests validate report parsing, not real bootability or the xorriso binary.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "scripts/verify-live-iso.sh"


class ISOVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.iso = self.base / "mock.iso"
        self.iso.write_bytes(b"not a real ISO")
        self.bin = self.base / "bin"
        self.bin.mkdir()

    def invoke(self, files: str, boots: str):
        script = self.bin / "xorriso"
        script.write_text(
            "#!/bin/sh\n"
            "case \"$*\" in\n"
            "  *-find*) cat <<'FILES'\n"
            + files
            + "\nFILES\n;;\n"
            "  *-report_el_torito*) cat <<'BOOTS'\n"
            + boots
            + "\nBOOTS\n;;\n"
            "  *) exit 2;;\n"
            "esac\n"
        )
        script.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(self.bin) + os.pathsep + env.get("PATH", "")
        env["LOCALZET_REPORT_DIR"] = str(self.base / "reports")
        return subprocess.run(
            ["bash", str(VERIFY), str(self.iso)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

    def test_recognises_all_required_files_and_both_boot_modes(self):
        result = self.invoke(
            "/casper/vmlinuz\n/casper/initrd\n/casper/filesystem.squashfs",
            "El Torito boot img :   1 BIOS y none\nEl Torito boot img :   2 UEFI y none",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("structural checks passed", result.stdout)

    def test_rejects_missing_casper_rootfs(self):
        result = self.invoke(
            "/casper/vmlinuz\n/casper/initrd",
            "El Torito boot img :   1 BIOS y none\nEl Torito boot img :   2 UEFI y none",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("filesystem.squashfs", result.stderr)

    def test_rejects_missing_uefi_boot(self):
        result = self.invoke(
            "/casper/vmlinuz\n/casper/initrd\n/casper/filesystem.squashfs",
            "El Torito boot img :   1 BIOS y none",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("UEFI", result.stderr)

    def test_rejects_missing_bios_boot(self):
        result = self.invoke(
            "/casper/vmlinuz\n/casper/initrd\n/casper/filesystem.squashfs",
            "El Torito boot img :   1 UEFI y none",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BIOS", result.stderr)


if __name__ == "__main__":
    unittest.main()
