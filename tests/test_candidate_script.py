import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("candidate", ROOT / "scripts/qemu-interactive-install-smoke.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CandidateScriptTests(unittest.TestCase):
    def test_full_candidate_assertions_are_present(self):
        script = module.installed_script("complete", True, True, True, True)
        for marker in ("installed Executive Files window was active over a populated user fixture", "LOCALZET_CANDIDATE_FILES_CAPTURE_READY",
                       "LOCALZET_CANDIDATE_STILL_LOCKED", "LOCALZET_CANDIDATE_OFFICE_PNG",
                       "installed native ONLYOFFICE launched", "Localzet-offline-review.docx", "Fixture heading ink"):
            self.assertIn(marker, script)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)

    def test_installed_files_has_a_separate_real_screen_capture(self):
        script = module.installed_script("complete", native_files=True)
        self.assertIn("launch_app_x11 localzet-candidate-nautilus /usr/bin/nautilus", script)
        self.assertIn("/usr/bin/nautilus --new-window", script)
        self.assertIn('busctl --user list --no-pager', script)
        self.assertIn("org.gnome.Nautilus", script)
        self.assertIn("getwindowname", script)
        self.assertIn("Localzet Visual Fixture", script)
        self.assertIn("grep -Fq", script)
        self.assertIn("LOCALZET_CANDIDATE_FILES_CAPTURE_READY", script)
        source = (ROOT / "scripts/qemu-interactive-install-smoke.py").read_text()
        self.assertIn('self.capture("files")', source)
        self.assertIn('files_screen = installed.screen.with_name(f"{installed.screen.stem}-files.ppm")', source)
        self.assertIn("Installed Files window evidence", source)

    def test_minimal_candidate_is_unchanged(self):
        script = module.installed_script()
        self.assertNotIn("installed Executive Files window was active", script)
        self.assertNotIn("LOCALZET_CANDIDATE_OFFICE_GEOMETRY", script)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)

    def test_office_diagnostics_are_explicit(self):
        normal = module.installed_script("complete", True, True, True, True)
        software = module.installed_script("complete", True, True, True, True, "software-disable-gpu")
        self.assertIn("Office diagnostic mode: default", normal)
        self.assertIn("Office diagnostic mode: software-disable-gpu", software)
        # The default command stays unmodified; only the wrapper adds
        # --disable-gpu after detecting a virtio display adapter at runtime.
        self.assertIn('/usr/bin/localzet-office  "$office_dir/Localzet-offline-review.docx"', normal)
        self.assertNotIn('/usr/bin/localzet-office --disable-gpu', normal)
        self.assertIn('if [[ "$virtio_gpu" == 1 ]]; then', normal)
        self.assertIn("grep -Fq -- '--disable-gpu'", normal)
        self.assertNotIn("--setenv=LIBGL_ALWAYS_SOFTWARE=1", normal)
        self.assertIn("--disable-gpu", software)
        self.assertNotIn("--setenv=LIBGL_ALWAYS_SOFTWARE=1", software)
        self.assertNotIn("--setenv=QT_OPENGL=software", software)
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
                       "localzet-installed-rootless-fixture:ci", "/usr/bin/busybox",
                       "ROOTLESS_OK", "PERSISTENCE_OK"):
            self.assertIn(marker, script)
        # Verify the actual restart/persistence sequence, not a log string.
        stopped = script.index('change("stop")')
        restarted = script.index('assert change("start") == "rootless подтверждён"', stopped)
        inspected = script.index('run("image", "inspect", tag)', restarted)
        persisted = script.index(
            'run("run", "--rm", "--network", "none", tag, "/bin/busybox", "echo", "PERSISTENCE_OK")',
            inspected,
        )
        self.assertLess(stopped, restarted)
        self.assertLess(restarted, inspected)
        self.assertLess(inspected, persisted)
        self.assertNotIn('run("image", "rm", tag)', script)
        self.assertIn('mktemp -d "$HOME/.localzet-wine-ci.XXXXXXXX"', script)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)

    def test_installed_office_uses_product_launcher(self):
        script = module.installed_script("complete", False, True, True)
        self.assertIn('/usr/bin/localzet-office RENDER_FLAGS'.replace(" RENDER_FLAGS", " "), script)
        self.assertIn("test -x /usr/bin/localzet-office", script)
        self.assertIn("/usr/local/share/applications/", script)
        # ONLYOFFICE is single-instance: opening a blank window first would
        # make the later fixture invocation forward to a renderer started
        # without the candidate's per-process GPU policy.
        self.assertNotIn("launch_app localzet-office", script)
        self.assertEqual(script.count('/usr/bin/localzet-office  "$office_dir/Localzet-offline-review.docx"'), 1)
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

    def test_network_preload_requires_offline_installer_and_route_checks(self):
        script = module.installed_script("complete", network_preload=True)
        for marker in ("PKEXEC_UID=", "cached NetBird installed offline", "preinstalled UserNet launched",
                       "network-before.json", "network-after.json", "usernet-helper.service",
                       "netbird_0.83.1_linux_amd64.deb"):
            self.assertIn(marker, script)
        self.assertNotIn("cached NetBird installed offline", module.installed_script())
        with self.assertRaises(ValueError):
            module.installed_script("standard", network_preload=True)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)

    def test_network_preload_denies_enabled_helper_and_unexpected_tunnel(self):
        script = module.installed_script("complete", network_preload=True)
        self.assertIn("Unexpected UserNet helper or NetBird tunnel", script)
        self.assertNotIn("! systemctl is-enabled --quiet usernet-helper.service", script)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)

    def test_rootless_engine_releases_only_prior_test_units(self):
        script = module.installed_script("complete", True)
        self.assertIn('unit="localzet-candidate-$app.service"', script)
        self.assertIn('systemctl --user stop "$unit"', script)
        self.assertIn('pgrep -u localzet-test -f /usr/bin/localzet-containers', script)
        self.assertIn("installed unprivileged container executed offline", script)
        self.assertIn('run("image", "inspect", tag)', script)
        self.assertIn('"PERSISTENCE_OK"', script)
        self.assertNotIn('run("image", "rm", tag)', script)
        self.assertNotIn("pkill", script)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)


    def test_ci_kvm_acl_is_refreshed_after_live_guest_without_host_side_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            device = Path(directory) / "kvm"
            device.touch()
            with mock.patch.dict(module.os.environ, {"GITHUB_ACTIONS": "true"}):
                with mock.patch.object(module.os, "access", side_effect=[False, True]):
                    with mock.patch.object(module.subprocess, "run") as run:
                        self.assertTrue(module.ensure_ci_kvm_access(device))
            run.assert_called_once_with(
                ["sudo", "setfacl", "-m", f"u:{module.os.getuid()}:rw", str(device)],
                check=True,
                stdout=module.subprocess.PIPE,
                stderr=module.subprocess.PIPE,
                text=True,
                timeout=10,
            )

    def test_ci_kvm_acl_refresh_never_escalates_outside_github_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            device = Path(directory) / "kvm"
            device.touch()
            with mock.patch.dict(module.os.environ, {"GITHUB_ACTIONS": "false"}):
                with mock.patch.object(module.os, "access", return_value=False):
                    with mock.patch.object(module.subprocess, "run") as run:
                        self.assertFalse(module.ensure_ci_kvm_access(device))
            run.assert_not_called()

    def test_installed_containers_has_a_distinct_live_window_capture(self):
        script = module.installed_script("complete", True)
        for marker in ("localzet-candidate-visual-fixture", "LOCALZET_CANDIDATE_CONTAINERS_CAPTURE_READY",
                       "LOCALZET_CANDIDATE_CONTAINERS_GEOMETRY", "Localzet Containers",
                       "getactivewindow", "xdotool search --onlyvisible --name 'Containers'",
                       "getwindowclassname", "installed rootless fixture is visible"):
            self.assertIn(marker, script)
        self.assertNotIn("xprop -root _NET_CLIENT_LIST", script)
        self.assertNotIn("xwininfo -root -tree", script)
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)
        source = (ROOT / "scripts/qemu-interactive-install-smoke.py").read_text()
        self.assertIn('self.capture("containers-installed")', source)
        self.assertIn("Installed Containers window evidence", source)
        self.assertIn("containers_screen.read_bytes() == office_screen.read_bytes()", source)
        self.assertNotIn('installed.capture("containers-installed")', source)
        # Stop any earlier test instance, then require a fresh window only
        # after the rootless engine and populated fixture are ready.
        self.assertIn("localzet-network localzet-containers; do", script)
        stale_check = script.index("Unexpected stale Localzet Containers process before rootless fixture")
        rootless_test = script.index("Installed rootless fixture is visible", script.index("def installed_script")) if "Installed rootless fixture is visible" in script else script.index("installed rootless fixture is visible")
        app_start = script.index("launch_app_x11 localzet-candidate-localzet-containers")
        self.assertLess(stale_check, rootless_test)
        self.assertLess(rootless_test, app_start)
        self.assertIn('if pgrep -u localzet-test -f "$pattern" >/dev/null; then return 0; fi', script[:app_start])
        self.assertIn("launch_app_x11 localzet-candidate-localzet-containers", script[app_start:])
        self.assertIn("com\\.localzet\\.Containers", script[app_start:])
