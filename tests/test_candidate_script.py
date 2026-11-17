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

    def test_combined_branded_packages_are_required(self):
        script = module.installed_script("complete", True, True, True, True, branded_control_center=True)
        for marker in ("installed branded Control Center package launched", "+localzet3",
                       "localzet-about-dark.svg", "control-center.BUILD-COMMIT",
                       "nautilus.BUILD-COMMIT", "launch_app gnome-control-center"):
            self.assertIn(marker, script)
        self.assertIn("cmp /usr/share/doc/localzet-desktop/control-center.BUILD-COMMIT /usr/share/doc/localzet-desktop/nautilus.BUILD-COMMIT", script)
        self.assertNotIn("installed branded Control Center package launched", module.installed_script())
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)

    def test_windows_matrix_requires_real_msi_and_x86_in_installed_image(self):
        script = module.installed_script("complete", True, True, True, True, branded_control_center=True, windows_matrix=True)
        for marker in ("opt/localzet/fixture32/raw", "opt/localzet/msi/raw", "smoke32.exe --profile ci-smoke --run",
                       "fixture.msi --profile ci-msi --run", "Installed Wine x86 fixture exit code",
                       "LocalzetFixture/payload.txt", "cmp -", "distinct prefixes", "/usr/bin/timeout 840"):
            self.assertIn(marker, script)
        self.assertNotIn("smoke32.exe", module.installed_script())
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)
