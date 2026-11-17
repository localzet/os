"""Root-only CI fixture; never installs rules in the host namespace."""
import subprocess
import sys
import uuid
import json

from localzet.proxy_policy import render_policy


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def main():
    suffix = uuid.uuid4().hex[:8]
    client, peer = "lz-client-" + suffix, "lz-peer-" + suffix
    a, b = "a" + suffix, "b" + suffix
    created = []
    server = None

    def ns(name, *args, **kwargs):
        return run("ip", "netns", "exec", name, *args, **kwargs)

    def probe(address, port, udp=False, allowed=True):
        code = """import socket, sys
address, port, udp, allowed = sys.argv[1:]
family = socket.AF_INET6 if ':' in address else socket.AF_INET
with socket.socket(family, socket.SOCK_DGRAM if udp == '1' else socket.SOCK_STREAM) as s:
    s.settimeout(3)
    try:
        s.connect((address, int(port)))
        s.sendall(b'ping')
        success = s.recv(4) == b'pong'
    except OSError as exc:
        print(address, port, udp, repr(exc), file=sys.stderr)
        success = False
assert success == (allowed == '1'), (address, port, udp, success)
"""
        ns(client, sys.executable, "-c", code, address, str(port),
           str(int(udp)), str(int(allowed)))

    try:
        for name in (client, peer):
            run("ip", "netns", "add", name)
            created.append(name)
            ns(name, "ip", "link", "set", "lo", "up")
        run("ip", "link", "add", a, "netns", client, "type", "veth",
            "peer", "name", b, "netns", peer)
        for name, link, index in ((client, a, 1), (peer, b, 2)):
            ns(name, "ip", "addr", "add", f"192.0.2.{index}/24", "dev", link)
            ns(name, "ip", "-6", "addr", "add", f"2001:db8::{index}/64",
               "dev", link, "nodad")
            ns(name, "ip", "link", "set", link, "up")
        # Static neighbors make the fixture independent of IPv6 DAD/NDP timing.
        # The policy intentionally does not permit arbitrary ICMPv6 egress.
        for name, link, other, other_link, index in (
                (client, a, peer, b, 2), (peer, b, client, a, 1)):
            info = ns(other, "ip", "-j", "link", "show", "dev", other_link,
                      capture_output=True)
            mac = json.loads(info.stdout)[0]["address"]
            for family, address in (("-4", f"192.0.2.{index}"),
                                    ("-6", f"2001:db8::{index}")):
                ns(name, "ip", family, "neigh", "replace", address,
                   "lladdr", mac, "nud", "permanent", "dev", link)
            ns(name, "ip", "-6", "addr", "show", "dev", link)
        server_code = """import socket, selectors, signal
sel = selectors.DefaultSelector()
for family, address in ((socket.AF_INET, '192.0.2.2'), (socket.AF_INET6, '2001:db8::2')):
    for port, kind in ((7890, socket.SOCK_STREAM), (443, socket.SOCK_STREAM),
                       (53, socket.SOCK_DGRAM), (443, socket.SOCK_DGRAM),
                       (53, socket.SOCK_STREAM)):
        s = socket.socket(family, kind)
        s.bind((address, port))
        if kind == socket.SOCK_STREAM:
            s.listen()
        sel.register(s, selectors.EVENT_READ)
def stop_proxy(*_):
    for key in list(sel.get_map().values()):
        if key.fileobj.getsockname()[1] == 7890:
            sel.unregister(key.fileobj)
            key.fileobj.close()
    print('proxy stopped', flush=True)
signal.signal(signal.SIGUSR1, stop_proxy)
print('ready', flush=True)
while True:
    for key, _ in sel.select():
        s = key.fileobj
        if s.type == socket.SOCK_STREAM:
            conn, _ = s.accept()
            with conn:
                conn.settimeout(2)
                if conn.recv(4) == b'ping':
                    conn.sendall(b'pong')
        else:
            data, addr = s.recvfrom(4)
            if data == b'ping':
                s.sendto(b'pong', addr)
"""
        server = subprocess.Popen(["ip", "netns", "exec", peer, sys.executable,
                                   "-u", "-c", server_code], stdout=subprocess.PIPE, text=True)
        assert server.stdout.readline().strip() == "ready"
        cases = [(address, port, udp)
                 for address in ("192.0.2.2", "2001:db8::2")
                 for port, udp in ((7890, False), (443, False), (53, False),
                                   (53, True), (443, True))]
        for case in cases:
            probe(*case)
        ns(client, "nft", "-f", "-", input=render_policy("192.0.2.2", 7890))
        for case in cases:
            probe(*case, allowed=case == ("192.0.2.2", 7890, False))
        ns(client, "nft", "list", "table", "inet", "localzet_proxy_only")
        # Keep direct destinations alive when only the proxy fails.
        import signal
        server.send_signal(signal.SIGUSR1)
        assert server.stdout.readline().strip() == "proxy stopped"
        ns(peer, sys.executable, "-c",
           "import socket; s=socket.create_connection(('192.0.2.2',443),3); "
           "s.sendall(b'ping'); assert s.recv(4)==b'pong'; s.close()")
        for case in cases:
            probe(*case, allowed=False)
        print("PASS: isolated IPv4 proxy endpoint; direct TCP, UDP, DNS ports and IPv6 denied")
    finally:
        if server is not None and server.poll() is None:
            server.kill()
            server.wait()
        for name in reversed(created):
            run("ip", "netns", "delete", name)


if __name__ == "__main__":
    main()
