import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("overlay", Path(__file__).resolve().parents[1] / "scripts/install-office-desktop-overlay.py")
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)


class OfficeOverlayTests(unittest.TestCase):
    def test_preserves_mime_actions_and_vendor_desktop_identity(self):
        source = "[Desktop Entry]\nName=ONLYOFFICE\nExec=desktopeditors %U\nTryExec=/usr/bin/desktopeditors\nMimeType=application/msword;\nDBusActivatable=true\n[Desktop Action New]\nName=New\nExec=/usr/bin/onlyoffice-desktopeditors --new:word\n"
        result = overlay.transform(source)
        self.assertIn("Exec=/usr/bin/localzet-office %U", result)
        self.assertIn("TryExec=/usr/bin/localzet-office", result)
        self.assertIn("MimeType=application/msword;", result)
        self.assertIn("Exec=/usr/bin/localzet-office --new:word", result)
        self.assertIn("DBusActivatable=false", result)

    def test_refuses_unreviewed_exec_and_missing_primary(self):
        for source in ("[Desktop Entry]\nExec=sh -c evil\n", "[Desktop Entry]\nName=Office\n"):
            with self.assertRaises(ValueError):
                overlay.transform(source)


launcher_spec = importlib.util.spec_from_loader(
    "office_launcher",
    SourceFileLoader(
        "office_launcher",
        str(Path(__file__).resolve().parents[1] / "apps/localzet-office/localzet-office"),
    ),
)
launcher = importlib.util.module_from_spec(launcher_spec)
launcher_spec.loader.exec_module(launcher)


class OfficeLauncherTests(unittest.TestCase):
    def make_device(self, root, name, vendor, pci_class):
        device = root / name
        device.mkdir()
        (device / "vendor").write_text(vendor + "\n", encoding="ascii")
        (device / "class").write_text(pci_class + "\n", encoding="ascii")
        return device

    def test_virtio_display_gets_process_scoped_gpu_fallback(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_device(root, "0000:00:01.0", "0x1af4", "0x030000")
            self.assertEqual(
                launcher.command_for(["/tmp/review.docx"], root),
                ["/usr/bin/onlyoffice-desktopeditors", "--disable-gpu", "/tmp/review.docx"],
            )

    def test_physical_display_and_unrelated_virtio_devices_keep_native_gpu(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_device(root, "0000:01:00.0", "0x10de", "0x030000")
            self.make_device(root, "0000:00:02.0", "0x1af4", "0x020000")
            self.assertEqual(
                launcher.command_for(["/tmp/review.docx"], root),
                ["/usr/bin/onlyoffice-desktopeditors", "/tmp/review.docx"],
            )

    def test_explicit_diagnostic_flag_is_not_duplicated(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_device(root, "0000:00:01.0", "0x1af4", "0x030000")
            self.assertEqual(
                launcher.command_for(["--disable-gpu", "/tmp/review.docx"], root),
                ["/usr/bin/onlyoffice-desktopeditors", "--disable-gpu", "/tmp/review.docx"],
            )
