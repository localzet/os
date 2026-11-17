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

    # Drop all privilege before executing client code. This is a CI fixture,
    # not a desktop launcher or a general-purpose sandbox.
    client_command = ("ip", "netns", "exec", client, "setpriv",
                      "--reuid=65534", "--regid=65534", "--clear-groups",
                      "--bounding-set=-all", "--inh-caps=-all",
                      "--ambient-caps=-all", "--no-new-privs")

    def client_run(*args):
        return run(*client_command, *args)

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
        client_run(sys.executable, "-c", code, address, str(port),
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
        server_code = """import socket, selectors, signal, threading
def exact(conn, n):
    data = b''
    while len(data) < n:
        chunk = conn.recv(n - len(data))
        if not chunk:
            raise EOFError()
        data += chunk
    return data

def socks(conn):
    with conn:
        conn.settimeout(3)
        try:
            assert exact(conn, 3) == bytes([5, 1, 0])
            conn.sendall(bytes([5, 0]))
            assert exact(conn, 4) == bytes([5, 1, 0, 3])
            name = exact(conn, exact(conn, 1)[0])
            port = int.from_bytes(exact(conn, 2), 'big')
            assert name == b'fixture.invalid' and port == 443
            with socket.create_connection(('192.0.2.2', port), 3) as target:
                conn.sendall(bytes([5, 0, 0, 1, 0, 0, 0, 0, 0, 0]))
                target.sendall(exact(conn, 4))
                conn.sendall(exact(target, 4))
        except (OSError, EOFError, AssertionError):
            return

sel = selectors.DefaultSelector()
for family, address in ((socket.AF_INET, '192.0.2.2'), (socket.AF_INET6, '2001:db8::2')):
    for port, kind in ((7890, socket.SOCK_STREAM), (7891, socket.SOCK_STREAM), (443, socket.SOCK_STREAM),
                       (53, socket.SOCK_DGRAM), (443, socket.SOCK_DGRAM),
                       (53, socket.SOCK_STREAM)):
        s = socket.socket(family, kind)
        s.bind((address, port))
        if kind == socket.SOCK_STREAM:
            s.listen()
        sel.register(s, selectors.EVENT_READ)
def stop_proxy(*_):
    for key in list(sel.get_map().values()):
        if key.fileobj.getsockname()[1] in (7890, 7891):
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
            if s.getsockname()[1] == 7891:
                threading.Thread(target=socks, args=(conn,), daemon=True).start()
                continue
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
        # Exercise the IPv6 allow rule in the kernel, not just the renderer.
        ns(client, "nft", "-f", "-", input=(
            "delete table inet localzet_proxy_only\n" +
            render_policy("2001:db8::2", 7890)))
        for case in cases:
            probe(*case, allowed=case == ("2001:db8::2", 7890, False))
        # Replace the fixture policy atomically with the SOCKS endpoint.
        ns(client, "nft", "-f", "-", input=(
            "delete table inet localzet_proxy_only\n" +
            render_policy("192.0.2.2", 7891)))
        socks_probe = """import socket, sys
def exact(s, n):
    data = b''
    while len(data) < n:
        chunk = s.recv(n - len(data))
        if not chunk:
            raise EOFError()
        data += chunk
    return data
with socket.create_connection(('192.0.2.2', 7891), 3) as s:
    s.settimeout(3)
    s.sendall(bytes([5, 1, 0]))
    assert exact(s, 2) == bytes([5, 0])
    name = b'fixture.invalid'
    s.sendall(bytes([5, 1, 0, 3, len(name)]) + name + (443).to_bytes(2, 'big'))
    assert exact(s, 10) == bytes([5, 0, 0, 1, 0, 0, 0, 0, 0, 0])
    s.sendall(b'ping')
    assert exact(s, 4) == b'pong'
"""
        client_run(sys.executable, "-c", socks_probe)
        client_run(sys.executable, "-c", """import os, socket, ctypes, errno
assert os.getuid() == os.geteuid() == 65534
assert os.getgid() == os.getegid() == 65534
assert not os.getgroups()
with open('/proc/self/status') as status:
    fields = dict(line.split(':', 1) for line in status if ':' in line)
for name in ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb'):
    assert int(fields[name], 16) == 0, name
assert fields['NoNewPrivs'].strip() == '1'
for family, protocol in ((socket.AF_INET, socket.IPPROTO_ICMP),
                         (socket.AF_INET6, socket.IPPROTO_ICMPV6),
                         (socket.AF_PACKET, 0)):
    try:
        s = socket.socket(family, socket.SOCK_RAW, protocol)
    except PermissionError:
        pass
    else:
        s.close()
        raise AssertionError('raw socket permitted')
# Even re-entering our own network namespace requires CAP_SYS_ADMIN.
libc = ctypes.CDLL(None, use_errno=True)
with open('/proc/self/ns/net', 'rb') as ns:
    assert libc.setns(ns.fileno(), 0) == -1
    assert ctypes.get_errno() == errno.EPERM
""")
        for case in cases:
            probe(*case, allowed=False)
        # Keep direct destinations alive when only the proxy fails.
        import signal
        server.send_signal(signal.SIGUSR1)
        assert server.stdout.readline().strip() == "proxy stopped"
        ns(peer, sys.executable, "-c",
           "import socket; s=socket.create_connection(('192.0.2.2',443),3); "
           "s.sendall(b'ping'); assert s.recv(4)==b'pong'; s.close()")
        failed = subprocess.run([*client_command, sys.executable,
                                 "-c", socks_probe], capture_output=True, text=True)
        assert failed.returncode != 0, "SOCKS connection survived proxy shutdown"
        for case in cases:
            probe(*case, allowed=False)
        print("PASS: isolated IPv4 and IPv6 proxy endpoints; direct TCP, UDP and DNS denied")
    finally:
        if server is not None and server.poll() is None:
            server.kill()
            server.wait()
        for name in reversed(created):
            run("ip", "netns", "delete", name)


if __name__ == "__main__":
    main()
