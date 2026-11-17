import importlib.util
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("candidate", ROOT / "scripts/qemu-interactive-install-smoke.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CandidateScriptTests(unittest.TestCase):
    def test_full_candidate_assertions_are_present(self):
        script = module.installed_script("complete", True, True, True, True)
        for marker in ("installed Executive Files package launched", "sleep 30", "LOCALZET_CANDIDATE_STILL_LOCKED",
                       "LOCALZET_CANDIDATE_OFFICE_PNG", "installed native ONLYOFFICE launched", "Localzet-offline-review.docx", "Fixture heading ink"):
            self.assertIn(marker, script)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)

    def test_minimal_candidate_is_unchanged(self):
        script = module.installed_script()
        self.assertNotIn("installed Executive Files package launched", script)
        self.assertNotIn("LOCALZET_CANDIDATE_OFFICE_GEOMETRY", script)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)

    def test_office_diagnostics_are_explicit(self):
        normal = module.installed_script("complete", True, True, True, True)
        software = module.installed_script("complete", True, True, True, True, "software")
        self.assertIn("Office diagnostic mode: default", normal)
        self.assertIn("Office diagnostic mode: software", software)
        self.assertNotIn("--disable-gpu", normal)
        self.assertIn("--disable-gpu", software)
        self.assertIn("--setenv=LIBGL_ALWAYS_SOFTWARE=1", software)
        for script in (normal, software):
            self.assertIn("test -w", script)
            self.assertIn("LOCALZET_CANDIDATE_OFFICE_FAILED_PNG", script)
            self.assertNotIn("--no-sandbox", script)
            subprocess.run(["bash", "-n"], input=script, text=True, check=True)
        with self.assertRaises(ValueError):
            module.installed_script(office_render_mode="software")
