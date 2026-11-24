import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class AssetsTests(unittest.TestCase):
    def test_gnome_metadata(self):
        folder = ROOT / 'extensions' / 'localzet-shell@localzet.com'
        metadata = json.loads((folder / 'metadata.json').read_text())
        self.assertEqual(metadata['uuid'], folder.name)
        self.assertIn('50', metadata['shell-version'])
        self.assertTrue((folder / 'extension.js').is_file())

    def test_design_tokens(self):
        data = json.loads((ROOT / 'assets/design-tokens.json').read_text())
        self.assertIn('accent', data['colors'])
        self.assertEqual(set(data['themes']), {'blue', 'purple', 'black'})
        self.assertEqual(data['themes']['blue']['accent'], '#5799f5')
        self.assertEqual(data['themes']['purple']['accent'], '#bb84e8')
        self.assertEqual(data['themes']['black']['accent'], '#b476ed')

    def test_wallpaper_is_svg(self):
        root = ET.parse(ROOT / 'assets/wallpapers/aurora.svg').getroot()
        self.assertEqual(root.tag, '{http://www.w3.org/2000/svg}svg')

    def test_approved_wallpaper_variants_are_webp(self):
        for theme in ('blue', 'purple', 'black'):
            content = (ROOT / f'assets/wallpapers/aurora-{theme}.webp').read_bytes()
            with self.subTest(theme=theme):
                self.assertEqual(content[:4], b'RIFF')
                self.assertEqual(content[8:12], b'WEBP')

    def test_shell_settings_schema_declares_themes_and_dock_pins(self):
        schema = ET.parse(
            ROOT / 'extensions/localzet-shell@localzet.com/schemas/com.localzet.shell.gschema.xml'
        ).getroot()
        self.assertEqual(schema.find('./schema').get('id'), 'com.localzet.shell')
        keys = {item.get('name') for item in schema.findall('./schema/key')}
        self.assertEqual(keys, {'appearance', 'pinned-apps'})

    def test_shell_appearance_classes_use_styled_widget_and_qemu_capture(self):
        extension = (ROOT / 'extensions/localzet-shell@localzet.com/extension.js').read_text()
        capture = (ROOT / 'scripts/qemu-live-visual.py').read_text()
        self.assertIn('const uiGroup = Main.layoutManager.uiGroup;', extension)
        self.assertIn('uiGroup.add_style_class_name(appearance)', extension)
        self.assertIn('uiGroup.remove_style_class_name(appearance)', extension)
        self.assertNotIn('global.stage.add_style_class_name', extension)
        self.assertIn('QEMU QMP', capture)
        self.assertIn('qmp.execute("screendump"', capture)
        self.assertIn('vnc=unix:', capture)

    def test_appearance_boxed_lists_follow_each_aurora_surface(self):
        css = (ROOT / 'apps/localzet-settings/settings.css').read_text()
        for theme, surface in (
            ('blue', '#13203a'),
            ('purple', '#2f1a3e'),
            ('black', '#131318'),
        ):
            with self.subTest(theme=theme):
                selector = 'list.boxed-list'
                if theme != 'blue':
                    selector = f'.aurora-{theme} {selector}'
                self.assertIn(selector, css)
                self.assertIn(surface, css)

    def test_appearance_toasts_follow_each_aurora_surface(self):
        css = (ROOT / 'apps/localzet-settings/settings.css').read_text()
        for theme, surface in (
            ('blue', '#13203a'),
            ('purple', '#2f1a3e'),
            ('black', '#131318'),
        ):
            selector = 'window.localzet-settings toast'
            if theme != 'blue':
                selector = f'window.localzet-settings.aurora-{theme} toast'
            with self.subTest(theme=theme):
                self.assertIn(selector, css)
                self.assertIn(f'background-color: alpha({surface}, 0.97)', css)

    def test_live_iso_workflow_captures_screens_on_draft_pull_requests(self):
        workflow = (ROOT / '.github/workflows/live-iso.yml').read_text()
        self.assertIn('Capture real GNOME 50 Wayland scenes', workflow)
        self.assertIn('scripts/qemu-live-visual.py dist/localzet-dev.iso', workflow)
        self.assertNotIn('github.event.pull_request.draft == false', workflow)
        for path in ('extensions/**', 'apps/localzet-settings/**', 'theme/icons/**'):
            with self.subTest(path=path):
                self.assertIn(f"- '{path}'", workflow)

    def test_live_icon_resolution_uses_the_installed_gtk_theme(self):
        check = (ROOT / 'scripts/gnome-icon-resolution-smoke.py').read_text()
        self.assertIn('Gtk.IconTheme.get_for_display(display)', check)
        self.assertIn('resolved.is_relative_to(THEME_ROOT)', check)
        self.assertIn('LOCALZET_ICON_RESULT {status}', check)
