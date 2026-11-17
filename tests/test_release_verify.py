import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_verify", ROOT / "scripts/verify-release.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
FPR = "A" * 40
OTHER = "B" * 40


def valid_status(signer=FPR, primary=FPR, digest="8", signature_class="00"):
    return f"[GNUPG:] VALIDSIG {signer} 2026-11-17 1 0 4 0 22 {digest} {signature_class} {primary}\n"


class ReleaseStatusTests(unittest.TestCase):
    def test_primary_and_signing_subkey(self):
        module.verify_status(valid_status(), FPR)
        module.verify_status(valid_status(OTHER, FPR), FPR)

    def test_wrong_key_weak_hash_wrong_class_and_ambiguous_signatures(self):
        for status in (valid_status(primary=OTHER), valid_status(digest="2"),
                       valid_status(signature_class="01"), valid_status() * 2,
                       "", valid_status() + "[GNUPG:] REVKEYSIG A user\n",
                       "[GNUPG:] VALIDSIG\n"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                module.verify_status(status, FPR)

    def test_nonregular_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            target = directory / "regular"
            target.write_bytes(b"data")
            link = directory / "link"
            link.symlink_to(target)
            with self.assertRaises(OSError):
                module.bounded_read(link, 4096)
            with self.assertRaises(ValueError):
                module.bounded_read(target, 3)
            with self.assertRaises(ValueError):
                module.bounded_read(directory, 4096)


@unittest.skipUnless(shutil.which("gpg") and shutil.which("gpgv"), "requires GnuPG")
class ReleaseSignatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name)
        cls.home = cls.directory / "gnupg"
        cls.home.mkdir(mode=0o700)
        cls.command = ["gpg", "--homedir", str(cls.home), "--batch", "--yes",
                       "--pinentry-mode", "loopback", "--passphrase", ""]
        for user in ("Localzet fixture", "Untrusted fixture"):
            subprocess.run(cls.command + ["--quick-generate-key",
                           f"{user} <fixture@example.invalid>", "ed25519", "sign", "1d"],
                           check=True, capture_output=True, timeout=45)
        keys = subprocess.check_output(cls.command + ["--with-colons", "--list-keys"], text=True)
        cls.fingerprints = [line.split(":")[9] for line in keys.splitlines() if line.startswith("fpr:")]
        cls.keyring = cls.directory / "trusted.gpg"
        cls.keyring.write_bytes(subprocess.check_output(cls.command + ["--export"]))

    def setUp(self):
        self.iso = self.directory / "localzet-test.iso"
        self.iso.write_bytes(b"original synthetic ISO fixture")
        self.checksum = self.directory / "SHA256SUMS"
        self.signature = self.directory / "SHA256SUMS.sig"
        self.digest = hashlib.sha256(self.iso.read_bytes()).hexdigest()
        self.checksum.write_text(f"{self.digest}  {self.iso.name}\n")
        self.sign(self.fingerprints[0])

    def sign(self, fingerprint):
        subprocess.run(self.command + ["--local-user", fingerprint, "--digest-algo", "SHA256",
                       "--output", str(self.signature), "--detach-sign", str(self.checksum)],
                       check=True, capture_output=True, timeout=30)

    def verify(self, fingerprint=None):
        return module.verify(self.iso, self.checksum, self.signature, self.keyring,
                             fingerprint or self.fingerprints[0])

    def test_real_detached_signature(self):
        self.assertEqual(self.verify(), self.digest)

    def test_signed_by_other_key_in_same_keyring(self):
        self.sign(self.fingerprints[1])
        with self.assertRaisesRegex(ValueError, "pinned primary key"):
            self.verify()

    def test_altered_image(self):
        self.iso.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.verify()

    def test_altered_manifest(self):
        self.checksum.write_text(f"{'0' * 64}  {self.iso.name}\n")
        with self.assertRaisesRegex(ValueError, "signature"):
            self.verify()

    def test_signed_manifest_with_wrong_name_or_multiple_entries(self):
        for text in (f"{self.digest}  ../localzet-test.iso\n",
                     f"{self.digest}  other.iso\n",
                     f"{self.digest}  {self.iso.name}\n" * 2):
            self.checksum.write_text(text)
            self.sign(self.fingerprints[0])
            with self.assertRaisesRegex(ValueError, "canonical checksum"):
                self.verify()

    def test_short_fingerprint_and_invalid_signature(self):
        with self.assertRaisesRegex(ValueError, "full independently trusted"):
            self.verify("AABB")
        self.signature.write_bytes(b"not an OpenPGP signature")
        with self.assertRaisesRegex(ValueError, "signature"):
            self.verify()


if __name__ == "__main__":
    unittest.main()
