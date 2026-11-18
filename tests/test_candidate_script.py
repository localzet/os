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

    def test_isolated_office_is_a_separate_x11_diagnostic(self):
        normal = module.installed_script("complete", True, True, True)
        isolated = module.installed_script("complete", True, True, True, office_render_mode="isolated-x11")
        self.assertIn("Office diagnostic mode: isolated-x11", isolated)
        self.assertIn("/usr/bin/xvfb-run", isolated)
        self.assertIn("XDG_CONFIG_HOME", isolated)
        self.assertIn("Fixture heading ink", isolated)
        self.assertNotIn("office-isolated.sh", normal)
        self.assertNotIn("--no-sandbox", isolated)
        subprocess.run(["bash", "-n"], input=isolated, text=True, check=True)

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

    def test_foreign_disk_refusal_exercises_real_backend_and_blank_target(self):
        script = module.foreign_refusal_script("test-password-123", "usb")
        for marker in ("read_only_target_plan", "/usr/lib/localzet/installer-backend", "result.returncode == 2",
                       "Для первой версии отключите все остальные диски", "wipefs", "LOCALZET_CANDIDATE_FOREIGN_REFUSED"):
            self.assertIn(marker, script)
        self.assertNotIn("LOCALZET_CANDIDATE_INSTALLED", script)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)

    def test_installed_rootless_and_windows_shortcut_gates(self):
        script = module.installed_script("complete", True)
        self.assertIn("installed managed rootless Docker responded", script)
        self.assertIn('change("stop")', script)
        self.assertIn("Rootless test changed system Docker", script)
        self.assertIn("installed Windows menu shortcut roundtrip", script)
        self.assertIn("store.remove(key)", script)
        self.assertNotIn("installed managed rootless Docker responded", module.installed_script())
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)

    def test_office_fresh_profile_preserves_real_session(self):
        script = module.installed_script("complete", False, True, True, office_render_mode="fresh-profile")
        self.assertIn("Office diagnostic mode: fresh-profile", script)
        self.assertIn('--setenv=HOME="$office_dir/profile/home"', script)
        self.assertIn('--setenv=QT_QPA_PLATFORM=xcb --setenv=GDK_BACKEND=x11', script)
        self.assertNotIn("office-isolated.sh", script)
        self.assertNotIn("installed managed rootless Docker responded", script)
        self.assertNotIn("--no-sandbox", script)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)

    def test_installed_rootless_failure_records_guest_journal(self):
        script = module.installed_script("complete", True)
        self.assertIn("Installed rootless Docker failure diagnostics", script)
        self.assertIn("journalctl --user -u localzet-rootless-docker.service", script)
        self.assertIn("kernel.apparmor_restrict_unprivileged_userns", script)
        self.assertNotIn("sysctl -w", script)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)

    def test_installed_rootless_container_and_persistence_required(self):
        script = module.installed_script("complete", True)
        for marker in ("installed unprivileged container executed offline",
                       "installed rootless image persisted across restart",
                       "localzet-installed-rootless-fixture:ci", "/usr/bin/busybox",
                       "ROOTLESS_OK", "PERSISTENCE_OK"):
            self.assertIn(marker, script)
        self.assertIn('mktemp -d "$HOME/.localzet-wine-ci.XXXXXXXX"', script)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)

    def test_installed_office_uses_product_launcher(self):
        script = module.installed_script("complete", False, True, True)
        self.assertIn('/usr/bin/localzet-office RENDER_FLAGS'.replace(" RENDER_FLAGS", " "), script)
        self.assertIn("test -x /usr/bin/localzet-office", script)
        self.assertIn("/usr/local/share/applications/", script)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)

    def test_preloaded_telegram_requires_system_commit_and_real_sandbox(self):
        script = module.installed_script("complete", telegram=True)
        for marker in ("flatpak info --system --show-commit", "flatpak run --system org.telegram.desktop",
                       "flatpak ps --columns=application", "preloaded system Telegram app",
                       "telegram-review/refs.tsv"):
            self.assertIn(marker, script)
        self.assertNotIn("preloaded system Telegram app", module.installed_script())
        with self.assertRaises(ValueError):
            module.installed_script(telegram=True)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)
