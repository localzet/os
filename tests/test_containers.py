import json
import unittest
from unittest.mock import patch
from localzet.containers import Deployment, deployment_args, compose_document, Engine, EngineError, parse_inventory, parse_stacks, parse_resources

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
        metrics = {"ID": CID, "CPUPerc": "0.10%", "MemUsage": "1MiB / 1GiB", "MemPerc": "0.10%",
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

    def test_pull_requires_explicit_reference(self):
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        with patch.object(engine, "_run") as run, patch.object(engine, "resources", return_value=()):
            for reference in ("alpine", "--all-tags", "https://registry/image:tag", "user:password@registry/image:tag", "image:tag extra"):
                with self.assertRaises(EngineError):
                    engine.pull_image(reference)
            run.assert_not_called()
            for reference in ("alpine:3.22", "registry.example:5000/team/image:v1", "docker.io/library/alpine@sha256:" + CID):
                engine.pull_image(reference)
                run.assert_called_with("image", "pull", reference, timeout=600)

    def test_create_container_fixed_restricted_profile(self):
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        image = "sha256:" + CID
        with patch.object(engine, "_run") as run, patch.object(engine, "resources", return_value=({"ID": image},)), patch.object(engine, "inventory", return_value=()):
            for name, identity in (("--help", image), ("fixture", "alpine:latest"), ("fixture", "sha256:" + "b" * 64)):
                with self.assertRaises(EngineError):
                    engine.create_container(name, identity)
            run.assert_not_called()
            engine.create_container("fixture", image)
            run.assert_called_once_with("container", "create", "--name", "fixture", "--pull", "never",
                "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--user", "65534:65534", "--pids-limit", "256", "--memory", "512m", image)

    def test_create_container_rejects_existing_name(self):
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        with patch.object(engine, "_run") as run, patch.object(engine, "resources", return_value=({"ID": "sha256:" + CID},)), patch.object(engine, "inventory", return_value=parse_inventory(json.dumps(ROW))):
            with self.assertRaises(EngineError):
                engine.create_container("fixture", "sha256:" + CID)
            run.assert_not_called()

    def test_advanced_deployment_arguments(self):
        options = Deployment(network="bridge", ports=("8080:80/tcp", "5353:53/udp"),
            environment=("MODE=dev",), mounts=("fixture:/data:ro",), memory_mib=1024,
            cpus="1.5", restart="unless-stopped")
        args = deployment_args(options)
        for value in ("127.0.0.1:8080:80/tcp", "127.0.0.1:5353:53/udp", "MODE=dev",
                      "type=volume,source=fixture,target=/data,volume-nocopy,readonly",
                      "1024m", "1.5", "unless-stopped"):
            self.assertIn(value, args)

    def test_advanced_deployment_rejects_unsafe_options(self):
        for options in (
            Deployment(network="host"), Deployment(ports=("8080:80/tcp",)),
            Deployment(network="bridge", ports=("0:80/tcp",)),
            Deployment(network="bridge", ports=("8080:80/tcp", "08080:81/tcp")),
            Deployment(environment=("PATH",)), Deployment(environment=("A=1", "A=2")),
            Deployment(mounts=("/etc:/data:rw",)), Deployment(mounts=("fixture:/etc:ro",)),
            Deployment(mounts=("fixture:/data:ro", "other:/data/sub:rw")),
            Deployment(memory_mib=0), Deployment(cpus="NaN"), Deployment(restart="invalid"),
        ):
            with self.subTest(options=options), self.assertRaises(EngineError):
                deployment_args(options)

    def test_advanced_mount_rejects_driver_options(self):
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        image = "sha256:" + CID
        with patch.object(engine, "resources", side_effect=[({"ID": image},),
                ({"Name": "fixture", "Driver": "local", "Scope": "local"},)]), \
                patch.object(engine, "inventory", return_value=()), \
                patch.object(engine, "_run", return_value=json.dumps({"device": "/etc", "o": "bind"})) as run:
            with self.assertRaises(EngineError):
                engine.create_container("fixture", image, Deployment(mounts=("fixture:/data:ro",)))
            run.assert_called_once_with("volume", "inspect", "--format", "{{json .Options}}", "fixture")

    def test_compose_studio_generates_restricted_document(self):
        source = json.dumps({"services": {"app": {"image": "sha256:" + CID}}})
        document, names = compose_document(source)
        self.assertEqual(names, ("app",))
        service = json.loads(document)["services"]["app"]
        self.assertEqual(service["image"], "sha256:" + CID)
        self.assertEqual(service["pull_policy"], "never")
        self.assertEqual(service["network_mode"], "none")
        self.assertTrue(service["read_only"])
        self.assertEqual(service["cap_drop"], ["ALL"])

    def test_compose_studio_rejects_unreviewed_features(self):
        image = "sha256:" + CID
        for document in (
            {"services": {}}, {"include": "/etc/private", "services": {"app": {"image": image}}},
            {"services": {"app": {"image": image, "privileged": True}}},
            {"services": {"app": {"image": image, "build": "."}}},
            {"services": {"app": {"image": "alpine:latest"}}},
            {"services": {"app": {"image": image, "env_file": "/etc/shadow"}}},
            {"services": {"app": {"image": image, "volumes": ["/:/host"]}}},
        ):
            with self.subTest(document=document), self.assertRaises(EngineError):
                compose_document(json.dumps(document))
        for source in ('{"services":{},"services":{}}', "services:\n  app: {}", "x" * 65537):
            with self.assertRaises(EngineError):
                compose_document(source)

    def test_compose_validation_passes_only_generated_document(self):
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        from pathlib import Path
        def inspect(*args):
            self.assertEqual(args[:2], ("compose", "--project-directory"))
            self.assertEqual(args[3:7], ("--env-file", "/dev/null", "-p", "localzet-validation"))
            self.assertEqual(args[-2:], ("config", "--quiet"))
            document = json.loads(Path(args[-3]).read_text())
            self.assertEqual(document["services"]["app"]["network_mode"], "none")
            return ""
        with patch.object(engine, "_run", side_effect=inspect) as run:
            engine.validate_compose(json.dumps({"services": {"app": {"image": "sha256:" + CID}}}))
            run.assert_called_once()

    def test_managed_compose_rejects_unknown_action_and_missing_image(self):
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        source = json.dumps({"services": {"app": {"image": "sha256:" + CID}}})
        with patch.object(engine, "_run") as run, patch.object(engine, "resources", return_value=()):
            for action in ("prune", "up"):
                with self.assertRaises(EngineError):
                    engine.managed_compose(source, action)
            run.assert_not_called()

    def test_managed_compose_refuses_foreign_project(self):
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        source = json.dumps({"services": {"app": {"image": "sha256:" + CID}}})
        with patch.object(engine, "_run", side_effect=[json.dumps(CID), "{}"]) as run:
            with self.assertRaisesRegex(EngineError, "identity mismatch"):
                engine.managed_compose(source, "down")
            self.assertEqual(run.call_count, 2)

    def test_managed_compose_down_targets_exact_ids(self):
        import hashlib
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        source = json.dumps({"services": {"app": {"image": "sha256:" + CID}}})
        document, _ = compose_document(source)
        digest = hashlib.sha256(document.encode()).hexdigest()
        project = "localzet-studio-" + digest[:32]
        labels = json.dumps({"com.localzet.studio.document": digest,
                             "com.docker.compose.project": project,
                             "com.docker.compose.service": "app"})
        with patch.object(engine, "_run", side_effect=[json.dumps(CID), labels, "",
                json.dumps(CID), labels, "", ""]) as run:
            self.assertEqual(engine.managed_compose(source, "down"), project)
            self.assertEqual(run.call_args_list[-2].args, ("container", "stop", "--time", "10", CID))
            self.assertEqual(run.call_args_list[-1].args, ("container", "rm", CID))

    def test_studio_store_roundtrip_and_permissions(self):
        import tempfile
        from pathlib import Path
        from localzet.containers import StudioStore
        source = json.dumps({"services": {"app": {"image": "sha256:" + CID}}})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "studio"
            store = StudioStore(root)
            identity = store.save(source)
            self.assertEqual(store.projects(), (identity,))
            self.assertEqual(StudioStore(root).load(identity), source)
            self.assertEqual((root / (identity + ".json")).stat().st_mode & 0o777, 0o600)
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            with self.assertRaises(EngineError):
                store.load("../outside")
            target = root / (identity + ".json")
            target.write_text(json.dumps({"services": {"other": {"image": "sha256:" + CID}}}))
            with self.assertRaisesRegex(EngineError, "fingerprint"):
                store.load(identity)

    def test_studio_store_refuses_symlink_and_public_directory(self):
        import tempfile
        from pathlib import Path
        from localzet.containers import StudioStore
        source = json.dumps({"services": {"app": {"image": "sha256:" + CID}}})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "studio"
            store = StudioStore(root)
            identity = store.save(source)
            target = root / (identity + ".json")
            target.unlink()
            target.symlink_to("/etc/passwd")
            with self.assertRaises(OSError):
                store.load(identity)
            root.chmod(0o755)
            with self.assertRaises(EngineError):
                store.projects()

    def test_metric_sample_validates_percentages(self):
        from localzet.containers import metric_sample
        sample = metric_sample({"CPUPerc": "250.25%", "MemPerc": "42.5%"})
        self.assertEqual(sample.cpu, 250.25)
        self.assertEqual(sample.memory, 42.5)
        for cpu, memory in (("NaN%", "0%"), ("-1%", "0%"), ("1%", "101%"), ("1%", "none")):
            with self.assertRaises(EngineError):
                metric_sample({"CPUPerc": cpu, "MemPerc": memory})

    def test_builder_rejects_invalid_input_and_existing_tag(self):
        from pathlib import Path
        import tempfile
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with patch.object(engine, "_check") as check, patch.object(engine, "resources", return_value=({"Repository": "fixture", "Tag": "dev"},)):
                for tag, source, context in (("--help", "FROM scratch", path),
                    ("fixture", "FROM scratch", path), ("fixture:dev", "", path),
                    ("fixture:dev", "FROM scratch", Path("/")),
                    ("fixture:dev", "FROM scratch", Path("relative")),
                    ("fixture:dev", "FROM scratch", path)):
                    with self.assertRaises(EngineError):
                        engine.build_image(tag, source, context)
                check.assert_not_called()

    def test_builder_passes_exact_reviewed_source(self):
        from pathlib import Path
        import tempfile
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        source = "FROM scratch\nLABEL fixture=localzet\n"
        row = {"Repository": "fixture", "Tag": "dev"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with patch.object(engine, "_check"), patch.object(engine, "resources", side_effect=[(), (row,)]), patch("localzet.containers.subprocess.Popen") as popen:
                def start(args, **kwargs):
                    self.assertEqual(kwargs["stdin"].read(), source.encode())
                    self.assertEqual(args[-3:], ["--file", "-", str(path.resolve())])
                    self.assertIn("--pull=false", args)
                    self.assertIn("none", args)
                    proc = popen.return_value.__enter__.return_value
                    proc.wait.return_value = 0
                    proc.poll.return_value = 0
                    return popen.return_value
                popen.side_effect = start
                self.assertEqual(engine.build_image("fixture:dev", source, path), (row,))

    def test_build_argument_flags(self):
        from localzet.containers import build_argument_flags
        self.assertEqual(build_argument_flags(("MODE=dev", "EMPTY=")),
                         ("--build-arg", "MODE=dev", "--build-arg", "EMPTY="))
        for values in (("MODE",), ("--help=x",), ("A=1", "A=2"), ("A=bad\nvalue",)):
            with self.assertRaises(EngineError):
                build_argument_flags(values)

    def test_build_tail_is_bounded(self):
        import subprocess
        import sys
        from localzet.containers import read_build_tail, LOG_LIMIT
        with subprocess.Popen([sys.executable, "-c",
                "import sys; sys.stdout.write('a' * 300000 + 'END')"],
                stdout=subprocess.PIPE) as proc:
            tail = read_build_tail(proc, 10)
            self.assertEqual(proc.wait(timeout=5), 0)
        self.assertTrue(tail.startswith("[Earlier output omitted]"))
        self.assertTrue(tail.endswith("END"))
        self.assertLessEqual(len(tail), LOG_LIMIT + 32)

    def test_image_history_excludes_commands_and_comments(self):
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        identity = "sha256:" + CID
        raw = json.dumps({"ID": "<missing>", "CreatedSince": "1 hour ago", "Size": "0B",
                          "CreatedBy": "secret command", "Comment": "secret"})
        with patch.object(engine, "resources", return_value=({"ID": identity},)), patch.object(engine, "_run", return_value=raw) as run:
            self.assertEqual(engine.image_history(identity), ({"ID": "<missing>", "CreatedSince": "1 hour ago", "Size": "0B"},))
            run.assert_called_once_with("image", "history", "--no-trunc", "--format", "{{json .}}", identity)

    def test_registry_requires_explicit_destination(self):
        from localzet.containers import validate_registry_tag
        for reference in ("ghcr.io/team/app:v1", "docker.io/team/app:v1", "registry.example:5000/app:v1"):
            validate_registry_tag(reference, qualified=True)
        for reference in ("app:v1", "team/app:v1", "ghcr.io/team/app", "--all-tags",
                          "https://ghcr.io/team/app:v1", "user:token@ghcr.io/team/app:v1"):
            with self.assertRaises(EngineError):
                validate_registry_tag(reference, qualified=True)

    def test_registry_tag_does_not_overwrite(self):
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        identity = "sha256:" + CID
        row = {"ID": identity, "Repository": "team/app", "Tag": "v1"}
        with patch.object(engine, "_run") as run, patch.object(engine, "resources", return_value=(row,)):
            with self.assertRaises(EngineError):
                engine.tag_image(identity, "docker.io/team/app:v1")
            run.assert_not_called()
            engine.tag_image(identity, "ghcr.io/team/app:v2")
            run.assert_called_once_with("image", "tag", identity, "ghcr.io/team/app:v2")

    def test_registry_push_requires_matching_image_id(self):
        with patch("localzet.containers.os.geteuid", return_value=1000):
            engine = Engine()
        identity = "sha256:" + CID
        row = {"ID": identity, "Repository": "team/app", "Tag": "v1"}
        with patch.object(engine, "_run") as run, patch.object(engine, "resources", return_value=(row,)):
            for image, reference in (("sha256:" + "b" * 64, "docker.io/team/app:v1"),
                    (identity, "ghcr.io/team/app:v1"), (identity, "team/app:v1")):
                with self.assertRaises(EngineError):
                    engine.push_image(image, reference)
            run.assert_not_called()
            engine.push_image(identity, "docker.io/team/app:v1")
            run.assert_called_once_with("image", "push", "docker.io/team/app:v1", timeout=600)
