import io
import json
import unittest
from unittest.mock import patch
from localzet.ai_mcp import Session, serve


def request(method, params=None, id_=1):
    return {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}


class MCPTests(unittest.TestCase):
    def ready(self):
        session = Session()
        response = session.handle(request("initialize", {"protocolVersion": "2025-11-25"}))
        self.assertEqual(response["result"]["protocolVersion"], "2025-11-25")
        self.assertIsNone(session.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        return session

    def test_read_only_tools(self):
        session = self.ready()
        tools = session.handle(request("tools/list"))["result"]["tools"]
        self.assertEqual({t["name"] for t in tools}, {"system_info", "gpu_inventory"})
        self.assertTrue(all(t["annotations"]["readOnlyHint"] for t in tools))
        with patch("localzet.ai_mcp.os_info", return_value={"name": "Localzet OS"}):
            response = session.handle(request("tools/call", {"name": "system_info"}))
        self.assertEqual(json.loads(response["result"]["content"][0]["text"]), {"name": "Localzet OS"})
        for name, args in (("shell", {}), ("gpu_inventory", {"command": "install"})):
            self.assertIn("error", session.handle(request("tools/call", {"name": name, "arguments": args})))

    def test_lifecycle_and_stdio(self):
        self.assertIn("error", Session().handle(request("tools/list")))
        messages = [request("initialize", {"protocolVersion": "2025-11-25"}),
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                    request("tools/list", id_=2)]
        stdin = io.BytesIO(("\n".join(json.dumps(m) for m in messages) + "\n").encode())
        stdout = io.StringIO()
        serve(stdin, stdout)
        self.assertEqual([json.loads(line)["id"] for line in stdout.getvalue().splitlines()], [1, 2])
