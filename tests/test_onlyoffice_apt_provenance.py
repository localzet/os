from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OnlyOfficeAptProvenanceTests(unittest.TestCase):
    def test_signed_repo_is_scoped_and_pinned(self):
        script = (ROOT / "scripts/ci/onlyoffice-apt-provenance.sh").read_text()
        self.assertIn("E09CA29F6E178040EF22B4098320CA65CB2DE8E5", script)
        self.assertIn("1dd90cd46946ef5f765f7dfeec0a47079f86fef3", script)
        self.assertIn("signed-by=", script)
        self.assertIn("gpgv --status-fd", script)
        self.assertIn("Acquire::https::Verify-Peer=true", script)
        self.assertIn("Acquire::https::Verify-Host=true", script)

    def test_binary_and_corresponding_source_are_exact(self):
        script = (ROOT / "scripts/ci/onlyoffice-apt-provenance.sh").read_text()
        self.assertIn("10.0.0-169", script)
        self.assertIn("2190edb4022a2ac2f6eee0f78815520f0e4ece1e8a1097c645a6f9b225c8b59c", script)
        self.assertIn("apt_private download", script)
        self.assertIn("apt_private source", script)
        self.assertIn("DSC_VERSION", script)
        self.assertIn("source_dsc_sha256", script)

    def test_missing_source_index_is_a_successful_fail_closed_audit(self):
        script = (ROOT / "scripts/ci/onlyoffice-apt-provenance.sh").read_text()
        self.assertIn("block_expected", script)
        self.assertIn("Skipping acquire of configured file 'main/source/Sources'", script)
        self.assertIn('"authenticated": status == "verified"', script)
        binary_check = script.index('[[ "$BINARY_SHA" == "$EXPECTED_BINARY_SHA" ]]')
        blocked = script.index('block_expected "The signed ONLYOFFICE InRelease has no main/source/Sources index')
        source_download = script.index('apt_private source "$SOURCE_PACKAGE=$SOURCE_VERSION"')
        self.assertLess(binary_check, blocked)
        self.assertLess(blocked, source_download)

    def test_no_global_or_unauthenticated_apt_trust(self):
        script = (ROOT / "scripts/ci/onlyoffice-apt-provenance.sh").read_text().lower()
        for forbidden in ("trusted=yes", "allow-unauthenticated=true", "apt-key add",
                          "/etc/apt/sources.list.d", "curl | sudo", "wget | sudo"):
            self.assertNotIn(forbidden, script)


if __name__ == "__main__":
    unittest.main()
