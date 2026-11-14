import json
import unittest
from unittest.mock import patch
from localzet.containers import Engine, EngineError, parse_inventory, parse_stacks, parse_resources

CID = "a" * 64
ROW = {"ID": CID, "Names": "fixture", "Image": "fixture:local", "State": "running",
       "Status": "Up", "Ports": ""}


class ContainersTests(unittest.TestCase):
    def test_inventory(self):
        rows = parse_inventory(json.dumps(ROW))
        self.assertEqual(rows[0].id, CID)
        self.assertEqual(rows[0].name, "fixture")
        self.assertEqual(parse_inventory(""), ())

    def test_invalid_inventory(self):
        for output in ("not json", "{}", json.dumps({**ROW, "ID": "short"}),
                       "\n".join([json.dumps(ROW)] * 2)):
            with self.assertRaises(EngineError):
                parse_inventory(output)

    def test_root_rejected(self):
        with patch("localzet.containers.os.geteuid", return_value=0):
            with self.assertRaises(EngineError):
                Engine()

    def test_explicit_engine_and_allowlisted_action(self):
        with patch("localzet.containers.os.geteuid", return_value=1000), patch("localzet.containers.os.getuid", return_value=1000):
            engine = Engine()
            self.assertEqual(str(engine.socket), "/run/user/1000/docker.sock")
            self.assertEqual(str(Engine(rootful=True).socket), "/var/run/docker.sock")
        with patch.object(engine, "_run", return_value=json.dumps(ROW)) as run:
            for action, cid in (("rm", CID), ("start", "--help"), ("start", "fixture")):
                with self.assertRaises(EngineError):
                    engine.action(action, cid)
            run.assert_not_called()
            engine.action("stop", CID)
            self.assertEqual(run.call_args_list[1].args, ("container", "stop", "--time", "10", CID))

    def test_stale_id(self):
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        with patch.object(engine, "_run", return_value="") as run:
            with self.assertRaisesRegex(EngineError, "no longer exists"):
                engine.action("start", CID)
            run.assert_called_once()

    def test_metrics_validate_identity_and_shape(self):
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        metrics = {"ID": CID, "CPUPerc": "0.10%", "MemUsage": "1MiB / 1GiB",
                   "NetIO": "0B / 0B", "BlockIO": "0B / 0B", "PIDs": "1"}
        with patch.object(engine, "_run", side_effect=[json.dumps(ROW), json.dumps(metrics)]):
            self.assertEqual(engine.metrics(CID)["CPUPerc"], "0.10%")
        with patch.object(engine, "_run", side_effect=[json.dumps(ROW), json.dumps({**metrics, "ID": "b" * 64})]):
            with self.assertRaises(EngineError):
                engine.metrics(CID)

    def test_logs_reject_stale_id_before_subprocess(self):
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        with patch.object(engine, "_run", return_value=""), patch("localzet.containers.subprocess.Popen") as popen:
            with self.assertRaises(EngineError):
                engine.logs(CID)
            popen.assert_not_called()

    def test_compose_inventory(self):
        item = {"Name": "demo", "Status": "running(1)", "ConfigFiles": "/tmp/compose.yaml"}
        self.assertEqual(parse_stacks(json.dumps([item]))[0].name, "demo")
        self.assertEqual(parse_stacks("[]"), ())
        for data in ({}, [item, item], [{**item, "Name": 3}], [{}]):
            with self.assertRaises(EngineError):
                parse_stacks(json.dumps(data))

    def test_compose_list_never_opens_config_paths(self):
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        with patch.object(engine, "_run", return_value=json.dumps([
            {"Name": "demo", "Status": "exited(1)", "ConfigFiles": "/untrusted/path"}])) as run:
            self.assertEqual(engine.stacks()[0].config_files, "/untrusted/path")
            run.assert_called_once_with("compose", "ls", "--all", "--format", "json")

    def test_resource_inventory_allowlist(self):
        rows = {
            "images": {"Repository": "fixture", "Tag": "local", "ID": "sha256:" + CID, "Size": "1MB"},
            "volumes": {"Name": "fixture", "Driver": "local", "Scope": "local"},
            "networks": {"Name": "fixture", "ID": CID, "Driver": "bridge", "Scope": "local"},
        }
        for kind, row in rows.items():
            with self.subTest(kind=kind):
                self.assertEqual(parse_resources(kind, json.dumps({**row, "Labels": "private"})), (row,))
                self.assertEqual(parse_resources(kind, ""), ())
                for invalid in ("null", "[]", "{}", "not json", json.dumps({**row, next(iter(row)): 1})):
                    with self.assertRaises(EngineError):
                        parse_resources(kind, invalid)
        for kind in ("images", "networks"):
            with self.assertRaises(EngineError):
                parse_resources(kind, json.dumps({**rows[kind], "ID": "short"}))

    def test_resource_commands_are_fixed(self):
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        with patch.object(engine, "_run", return_value="") as run:
            for kind, command in (
                ("images", ("image", "ls", "--all", "--no-trunc")),
                ("volumes", ("volume", "ls")),
                ("networks", ("network", "ls", "--no-trunc")),
            ):
                self.assertEqual(engine.resources(kind), ())
                run.assert_called_with(*command, "--format", "{{json .}}")
            count = run.call_count
            with self.assertRaises(EngineError):
                engine.resources("prune")
            self.assertEqual(run.call_count, count)
