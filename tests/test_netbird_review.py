import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from localzet.netbird import parse_status, status

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fetch_netbird", ROOT / "scripts/fetch-netbird.py")
fetcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetcher)


class NetBirdReviewTests(unittest.TestCase):
    def test_pinned_assets(self):
        manifest = json.loads((ROOT / "config/upstream/netbird.json").read_text())
        for package in ("netbird", "netbird-ui"):
            url, asset = fetcher.spec(manifest, package)
            self.assertEqual(url, f"https://github.com/netbirdio/netbird/releases/download/v0.83.1/{asset['name']}")
            self.assertEqual(len(asset["sha256"]), 64)
        with self.assertRaises(ValueError):
            fetcher.spec(manifest, "unknown")
        manifest["version"] = "../untrusted"
        with self.assertRaises(ValueError):
            fetcher.spec(manifest, "netbird")

    def test_privacy_projection(self):
        result = parse_status(json.dumps({"daemonStatus": "Connected",
            "peers": {"total": 3, "connected": 2, "details": [{"publicKey": "private fixture"}]},
            "netbirdIp": "100.64.1.2", "management": {"url": "https://example.invalid"}}))
        self.assertEqual(result, {"state": "Connected", "total": 3, "connected": 2})

    def test_bad_counts_or_status(self):
        for data in ({"daemonStatus": "unknown"}, {"daemonStatus": "Connected", "peers": {"total": 1, "connected": 2}},
                     {"daemonStatus": "Idle", "peers": {"total": True}}, {"daemonStatus": "Idle", "peers": []}):
            with self.assertRaises(ValueError):
                parse_status(json.dumps(data))

    def test_missing_peer_summary_is_not_zero(self):
        self.assertEqual(parse_status('{"daemonStatus":"Connected"}'), {"state": "Connected"})
        self.assertEqual(parse_status('{"daemonStatus":"Idle","peers":{"total":0,"connected":0}}'),
                         {"state": "Idle", "total": 0, "connected": 0})
        for peers in (None, {}, {"total": 0}, {"connected": 0}):
            with self.subTest(peers=peers), self.assertRaises(ValueError):
                parse_status(json.dumps({"daemonStatus": "Connected", "peers": peers}))

    def test_missing_client_does_not_spawn_process(self):
        with patch("localzet.netbird.installed", return_value=False), patch("localzet.netbird.subprocess.run") as run:
            self.assertEqual(status(), {"state": "not-installed"})
            run.assert_not_called()
