import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/aurora-complete-rc.yml").read_text(encoding="utf-8")


class AuroraCompleteRcDistributionGateTests(unittest.TestCase):
    def test_iso_artifact_requires_verified_distribution_gate(self):
        blocks = re.findall(
            r"(?ms)^      - name: Upload distributable Complete RC image\n(.*?)(?=^      - |\Z)",
            WORKFLOW,
        )
        self.assertEqual(len(blocks), 1)
        self.assertIn("steps.distribution.outputs.allowed == 'true'", blocks[0])
        self.assertIn("dist/localzet-aurora-complete-rc.iso", blocks[0])

    def test_unverified_office_uploads_evidence_without_iso(self):
        self.assertIn('source.get("mapping_status") == "verified"', WORKFLOW)
        self.assertIn('licensing.get("redistribution_status") == "verified"', WORKFLOW)
        self.assertIn('updates.get("status") == "verified"', WORKFLOW)
        blocks = re.findall(
            r"(?ms)^      - name: Upload non-distributable Complete RC evidence \(without ISO\)\n(.*?)(?=^      - |\Z)",
            WORKFLOW,
        )
        self.assertEqual(len(blocks), 1)
        self.assertIn("dist/REDISTRIBUTION-BLOCKED.txt", blocks[0])
        self.assertNotIn("dist/localzet-aurora-complete-rc.iso\n", blocks[0])


    def test_legacy_cleanup_is_scoped_to_one_known_artifact(self):
        self.assertIn("actions: write", WORKFLOW)
        self.assertIn("actions/runs/46046427962/artifacts", WORKFLOW)
        self.assertIn('select(.name == "aurora-complete-rc-engineering-image")', WORKFLOW)
        self.assertIn("actions/\u0061rtifacts/${artifact_id}", WORKFLOW)
        self.assertIn("github.ref == 'refs/heads/integration/aurora-professional-candidate'", WORKFLOW)

    def test_evidence_artifact_is_not_the_iso(self):
        self.assertIn("aurora-complete-rc-non-distributable-evidence", WORKFLOW)
        self.assertIn("dist/localzet-aurora-complete-rc.iso.sha256", WORKFLOW)
        self.assertIn("The ISO artifact is enabled only when", (ROOT / "docs/design/ONLYOFFICE.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
