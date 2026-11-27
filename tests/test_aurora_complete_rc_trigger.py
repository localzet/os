import re
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/aurora-complete-rc.yml").read_text()


class AuroraCompleteRcTriggerTests(unittest.TestCase):
    def test_professional_candidate_push_runs_exact_complete_rc(self):
        self.assertRegex(
            WORKFLOW,
            r"(?ms)^  push:\n    branches: \[integration/aurora-professional-candidate\]",
        )
        self.assertIn(
            "github.ref == 'refs/heads/integration/aurora-professional-candidate'",
            WORKFLOW,
        )
        self.assertEqual(WORKFLOW.count("github.event_name == 'push'"), 3)
        self.assertEqual(WORKFLOW.count("LOCALZET_EXPERIMENTAL_TELEGRAM=1 LOCALZET_EXPERIMENTAL_NETWORK=1"), 1)
        self.assertIn("--expect-preloaded-telegram --expect-network-preload", WORKFLOW)
        self.assertIn("--expect-archive-profile complete", WORKFLOW)
        self.assertIn("--expect-office --expect-executive-review", WORKFLOW)
        self.assertIn("--expect-foreign-disk", WORKFLOW)

    def test_candidate_pull_request_uses_same_complete_preloads(self):
        self.assertIn("github.base_ref == 'integration/aurora-professional-candidate'", WORKFLOW)
        self.assertEqual(WORKFLOW.count("GITHUB_BASE_REF"), 3)
        self.assertIn("integration/aurora-professional-candidate]", WORKFLOW)

    def test_workflow_yaml_parses(self):
        result = subprocess.run(
            ["ruby", "-e", "require 'yaml'; YAML.parse_file(ARGV.fetch(0))", str(ROOT / ".github/workflows/aurora-complete-rc.yml")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
