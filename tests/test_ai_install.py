import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from localzet import ai_install as a
from localzet.ai_workspace import terminal_argv


class AIInstallTests(unittest.TestCase):
    def test_metadata_requires_fixed_release_and_digest(self):
        item = {"name": a.CODEX_ASSET, "size": 100, "digest": "sha256:" + "a"*64,
                "browser_download_url": "https://github.com/openai/codex/releases/download/rust-v" + a.CODEX_VERSION + "/" + a.CODEX_ASSET}
        data = {"tag_name": "rust-v" + a.CODEX_VERSION, "draft": False, "prerelease": False, "assets": [item]}
        self.assertEqual(a.codex_metadata(data)[1:], (100, "a"*64))
        with self.assertRaises(ValueError):
            a.codex_metadata({**data, "prerelease": True})
        with self.assertRaises(ValueError):
            a.codex_metadata({**data, "assets": [{**item, "digest": None}]})
    def test_version_and_launch_are_fixed(self):
        self.assertEqual(a.claude_version("2.1.314\n"), "2.1.314")
        for bad in ("../../evil", "latest", "2.1.3;sh"):
            with self.assertRaises(ValueError):
                a.claude_version(bad)
        self.assertEqual(terminal_argv("codex")[-2:], ("/usr/bin/localzet-ai", "codex"))
        self.assertEqual(terminal_argv("claude", True)[-2:], ("/usr/bin/localzet-ai-install", "claude"))
    def test_atomic_publish_keeps_previous_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "clients"
            binary = Path(tmp) / "codex"
            binary.write_bytes(b"original synthetic fixture")
            receipt = {"tool": "codex", "version": "1.2.3", "sha256": a.digest(binary)}
            current = a.publish(binary, receipt, root)
            self.assertEqual(current.read_bytes(), binary.read_bytes())
            second = {**receipt, "version": "1.2.4"}
            a.publish(binary, second, root)
            self.assertTrue((root / "1.2.3/codex").is_file())
            self.assertEqual(current.readlink(), Path("1.2.4/codex"))

    def test_proxy_is_explicit_and_no_bypass(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "fixture"
            def fake(cmd, **kwargs):
                target.write_bytes(b"test")
                self.assertIn("--proxy", cmd)
                self.assertEqual(cmd[cmd.index("--proxy")+1], "http://127.0.0.1:7890")
                self.assertEqual(cmd[cmd.index("--noproxy")+1], "")
                self.assertEqual(cmd[cmd.index("--proto-redir")+1], "=https")
            with patch.object(a.subprocess, "run", side_effect=fake):
                a.download("https://example.invalid/fixture", target, 10, "http://127.0.0.1:7890")
