#!/usr/bin/env python3
"""Disposable runner: verify a host endpoint is reached only through relay."""
import http.server
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"localzet-proxy-proof")

server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
port = server.server_port
with tempfile.TemporaryDirectory(prefix="ai-smoke-") as directory:
    path = Path(directory) / "relay"
    relay = subprocess.Popen(["/usr/bin/socat", f"UNIX-LISTEN:{path},fork,mode=0600",
                             f"TCP4:127.0.0.1:{port}"])
    try:
        for _ in range(40):
            if path.is_socket():
                break
            time.sleep(.05)
        else:
            raise RuntimeError("Host relay did not start")
        child = r"""
set -eu
/usr/bin/socat TCP4-LISTEN:18080,bind=127.0.0.1,reuseaddr,fork UNIX-CONNECT:/run/localzet-ai/relay &
pid=$!
trap 'kill "$pid" 2>/dev/null || true' EXIT
/usr/bin/python3 - "$1" <<'PY'
import socket, sys, time, urllib.request
port = int(sys.argv[1])
for _ in range(40):
    try:
        with socket.create_connection(("127.0.0.1", 18080), timeout=.1):
            break
    except OSError:
        time.sleep(.05)
else:
    raise SystemExit("Missing isolated relay")
try:
    with socket.create_connection(("127.0.0.1", port), timeout=.5):
        raise SystemExit("Host loopback was reachable directly")
except OSError:
    pass
try:
    with socket.create_connection(("192.0.2.1", 443), timeout=.5):
        raise SystemExit("Direct external TCP was reachable")
except OSError:
    pass
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
assert opener.open("http://127.0.0.1:18080/", timeout=3).read() == b"localzet-proxy-proof"
print("Host direct path blocked; isolated relay works")
PY
"""
        subprocess.run(["/usr/bin/bwrap", "--die-with-parent", "--unshare-net",
                        "--unshare-pid", "--ro-bind", "/", "/", "--proc", "/proc",
                        "--dev", "/dev", "--tmpfs", "/run", "--tmpfs", "/tmp",
                        "--dir", "/run/localzet-ai", "--ro-bind", str(path), "/run/localzet-ai/relay",
                        "/bin/sh", "-c", child, "smoke", str(port)], check=True, timeout=20)
    finally:
        relay.terminate()
        relay.wait(timeout=5)
        server.shutdown()
