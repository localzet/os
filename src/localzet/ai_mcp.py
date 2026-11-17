"""Localzet MCP over stdio: read-only, no subprocesses or network."""
from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
MAX_LINE = 65536
TOOLS = {
    "system_info": "Read the running Localzet OS release, kernel and architecture.",
    "gpu_inventory": "Read PCI graphics devices and bound driver; no activation or installation.",
}


def os_info():
    from localzet.hardware import secure_boot
    release = platform.freedesktop_os_release()
    return {"name": release.get("PRETTY_NAME", release.get("NAME", "Linux")),
            "version": release.get("VERSION_ID", ""), "kernel": platform.release(),
            "architecture": platform.machine(), "secure_boot": secure_boot()}


def gpu_info():
    from localzet.hardware import inventory, plan
    report = plan(inventory())
    return {"graphics": report["graphics"], "nvidia_detected": report["nvidia_gpu_detected"],
            "mode": "read-only"}


def error(id_, code, message):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


class Session:
    def __init__(self):
        self.negotiated = False
        self.ready = False

    def handle(self, req):
        if not isinstance(req, dict) or req.get("jsonrpc") != "2.0" or not isinstance(req.get("method"), str):
            return error(None, -32600, "Invalid request")
        method, id_ = req["method"], req.get("id")
        has_id = "id" in req
        if has_id and (type(id_) not in (str, int) or id_ is None):
            return error(None, -32600, "Invalid request id")
        params = req.get("params", {})
        if not isinstance(params, dict):
            return error(id_, -32602, "Invalid params") if has_id else None
        if not has_id:
            if method == "notifications/initialized" and self.negotiated:
                self.ready = True
            return None
        if method == "initialize":
            version = params.get("protocolVersion")
            if not isinstance(version, str):
                return error(id_, -32602, "Protocol version required")
            self.negotiated = True
            self.ready = False
            result = {"protocolVersion": version if version in VERSIONS else VERSIONS[0],
                      "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": {"name": "localzet-system", "version": "0.1.0"}}
        elif method == "ping":
            result = {}
        elif not self.ready:
            return error(id_, -32002, "Initialize first")
        elif method == "tools/list":
            result = {"tools": [{"name": name, "description": detail,
                      "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
                      "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}}
                      for name, detail in TOOLS.items()]}
        elif method == "tools/call":
            name, arguments = params.get("name"), params.get("arguments", {})
            if not isinstance(name, str) or name not in TOOLS or arguments != {}:
                return error(id_, -32602, "Unknown tool or invalid arguments")
            try:
                value = {"system_info": os_info, "gpu_inventory": gpu_info}[name]()
                result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}]}
            except (OSError, ValueError, RuntimeError):
                result = {"content": [{"type": "text", "text": "Local diagnostics unavailable"}], "isError": True}
        else:
            return error(id_, -32601, "Method not found")
        return {"jsonrpc": "2.0", "id": id_, "result": result}


def serve(stdin=None, stdout=None):
    stdin = sys.stdin.buffer if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    session = Session()
    while True:
        raw = stdin.readline(MAX_LINE + 1)
        if not raw:
            return
        if len(raw) > MAX_LINE:
            # Reject the stream rather than process a partial JSON message.
            print(json.dumps(error(None, -32700, "Message too large")), file=stdout, flush=True)
            return
        try:
            req = json.loads(raw)
        except (ValueError, UnicodeError):
            reply = error(None, -32700, "Parse error")
        else:
            reply = session.handle(req)
        if reply is not None:
            print(json.dumps(reply, ensure_ascii=False, separators=(",", ":")), file=stdout, flush=True)


if __name__ == "__main__":
    serve()
