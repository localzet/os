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

    def test_resource_creation_rejects_invalid_names_and_existing_resources(self):
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        with patch.object(engine, "_run", return_value="") as run:
            for kind, name in (("images", "fixture"), ("volumes", "--help"), ("networks", "a/b"), ("volumes", "a")):
                with self.assertRaises(EngineError):
                    engine.create_resource(kind, name)
            run.assert_not_called()
        with patch.object(engine, "resources", return_value=({"Name": "fixture"},)), patch.object(engine, "_run") as run:
            with self.assertRaises(EngineError):
                engine.create_resource("volumes", "fixture")
            run.assert_not_called()

    def test_resource_creation_fixed_arguments(self):
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        with patch.object(engine, "resources", return_value=()), patch.object(engine, "_run") as run:
            engine.create_resource("volumes", "fixture")
            run.assert_called_with("volume", "create", "--driver", "local", "fixture")
            engine.create_resource("networks", "fixture")
            run.assert_called_with("network", "create", "--driver", "bridge", "--internal", "fixture")

    def test_resource_removal_guards(self):
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        with patch.object(engine, "_run") as run, patch.object(engine, "resources", return_value=()):
            for kind, identity in (("volumes", "fixture"), ("images", "short"), ("networks", CID)):
                with self.assertRaises(EngineError):
                    engine.remove_resource(kind, identity)
            run.assert_not_called()
        with patch.object(engine, "_run") as run, patch.object(engine, "resources", return_value=({"ID": CID, "Name": "bridge", "Scope": "local"},)):
            with self.assertRaises(EngineError):
                engine.remove_resource("networks", CID)
            run.assert_not_called()
        image = {"ID": "sha256:" + CID}
        with patch.object(engine, "_run") as run, patch.object(engine, "resources", return_value=(image, image)):
            with self.assertRaises(EngineError):
                engine.remove_resource("images", image["ID"])
            run.assert_not_called()

    def test_resource_removal_no_force(self):
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        image = {"ID": "sha256:" + CID}
        network = {"ID": CID, "Name": "fixture", "Scope": "local"}
        with patch.object(engine, "_run") as run, patch.object(engine, "resources", return_value=(image,)):
            engine.remove_resource("images", image["ID"])
            run.assert_called_once_with("image", "rm", "--no-prune", image["ID"])
        with patch.object(engine, "_run") as run, patch.object(engine, "resources", return_value=(network,)):
            engine.remove_resource("networks", CID)
            run.assert_called_once_with("network", "rm", CID)
