from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/nautilus-bundle-checksums.sh"


class NautilusBundleChecksumTests(unittest.TestCase):
    def test_canonical_basenames_and_stable_order(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)
            files = {"nautilus_50.2.2+localzet1_amd64.deb": b"test-one",
                     "nautilus-data_50.2.2+localzet1_all.deb": b"test-two",
                     "libnautilus-extension4_50.2.2+localzet1_amd64.deb": b"test-three"}
            for name, content in files.items():
                (path / name).write_bytes(content)
            result = subprocess.check_output(["bash", str(SCRIPT), directory], text=True)
            expected = sorted(hashlib.sha256(content).hexdigest() + "  " + name
                              for name, content in files.items())
            self.assertEqual(result.splitlines(), expected)
            self.assertNotIn("./", result)
            (path / "SHA256SUMS").write_text(result)
            subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=path, check=True)
            (path / next(iter(files))).write_bytes(b"tampered")
            self.assertNotEqual(subprocess.check_output(["bash", str(SCRIPT), directory], text=True), result)

    def test_invalid_file_count_or_symlink(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)
            for name in ("a.deb", "b.deb"):
                (path / name).write_bytes(b"test")
            self.assertNotEqual(subprocess.run(["bash", str(SCRIPT), directory], capture_output=True).returncode, 0)
            (path / "c.deb").symlink_to(path / "a.deb")
            self.assertNotEqual(subprocess.run(["bash", str(SCRIPT), directory], capture_output=True).returncode, 0)
