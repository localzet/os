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
