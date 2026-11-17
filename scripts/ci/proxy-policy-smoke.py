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
        # Network namespaces isolate abstract UNIX sockets, but not pathname
        # sockets. A desktop launcher will need a separate IPC boundary.
        import socket
        abstract = chr(0) + "lz-proxy-" + suffix
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as host_socket:
            host_socket.bind(abstract)
            host_socket.listen()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as control:
                control.connect(abstract)
                conn, _ = host_socket.accept()
                conn.close()
            # Deliberately mark the host socket inheritable. The subprocess
            # boundary must still close it before entering the namespace.
            host_socket.set_inheritable(True)
            client_run(sys.executable, "-c", """import errno, os, socket, sys
fd = int(sys.argv[1])
try:
    os.fstat(fd)
except OSError as exc:
    assert exc.errno == errno.EBADF
else:
    raise AssertionError('inherited host socket descriptor')
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
    s.settimeout(2)
    try:
        s.connect(chr(0) + sys.argv[2])
    except OSError as exc:
        assert exc.errno == errno.ECONNREFUSED, exc
    else:
        raise AssertionError('host abstract socket reachable')
""", str(host_socket.fileno()), abstract[1:])
        # A private mount namespace must hide pathname sockets too. Demonstrate
        # both the leak without mount isolation and denial with it, using a
        # synthetic session bus directory rather than the runner's real IPC.
        import tempfile
        import os
        with tempfile.TemporaryDirectory(prefix="lz-ipc-") as directory:
            os.chmod(directory, 0o755)
            pathname = os.path.join(directory, "bus")
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as bus:
                bus.bind(pathname)
                os.chmod(pathname, 0o777)
                bus.listen()
                ipc_probe = """import socket, sys, errno
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
    s.settimeout(2)
    try:
        s.connect(sys.argv[1])
    except OSError as exc:
        assert sys.argv[2] == 'deny' and exc.errno == errno.ENOENT, exc
    else:
        assert sys.argv[2] == 'allow', 'pathname IPC escaped isolation'
"""
                client_run(sys.executable, "-c", ipc_probe, pathname, "allow")
                conn, _ = bus.accept()
                conn.close()
                # Mount only inside a private mount namespace, before dropping
                # privileges. No changes to host mounts or real session buses.
                ns(client, "unshare", "--mount", "--propagation", "private",
                   "sh", "-eu", "-c",
                   'mount -t tmpfs -o mode=0755,nosuid,nodev,noexec tmpfs "$1"; shift; exec "$@"',
                   "sh", directory, *client_command[4:], sys.executable,
                   "-c", ipc_probe, pathname, "deny")
                # The host socket must remain reachable after the test.
                client_run(sys.executable, "-c", ipc_probe, pathname, "allow")
                conn, _ = bus.accept()
                conn.close()
        # Bubblewrap uses an allowlisted root instead of masking selected host
        # directories. Keep the existing filtered network namespace; never
        # request a new network namespace that would discard its policy.
        sandbox = ("bwrap", "--unshare-pid", "--unshare-ipc",
                   "--die-with-parent", "--new-session", "--clearenv",
                   "--ro-bind", "/usr", "/usr",
                   "--symlink", "usr/bin", "/bin",
                   "--symlink", "usr/lib", "/lib",
                   "--symlink", "usr/lib64", "/lib64",
                   "--proc", "/proc", "--dev", "/dev",
                   "--tmpfs", "/tmp", "--dir", "/run",
                   "--dir", "/home", "--chdir", "/tmp",
                   "--cap-drop", "ALL",
                   "--cap-add", "CAP_SETUID", "--cap-add", "CAP_SETGID",
                   "--cap-add", "CAP_SETPCAP", "--setenv", "PATH", "/usr/bin")
        def sandbox_run(code, *args):
            # Root creates the mount boundary; setpriv then drops every
            # capability and group before any fixture application executes.
            # Do not create a user namespace owning a different network.
            ns(client, *sandbox, *client_command[4:],
               "/usr/bin/python3", "-c", code, *args)

        sandbox_run("""import os, socket, sys
assert os.getuid() == os.geteuid() == 65534
assert os.getgid() == os.getegid() == 65534
assert not os.getgroups()
assert not os.path.exists('/run/dbus/system_bus_socket')
assert not os.path.exists('/run/user')
assert not os.path.exists('/etc')
assert not os.listdir('/home')
assert 'DBUS_SESSION_BUS_ADDRESS' not in os.environ
assert 'DISPLAY' not in os.environ
assert 'WAYLAND_DISPLAY' not in os.environ
assert os.readlink('/proc/self/ns/net') == sys.argv[1]
with open('/proc/self/status') as status:
    fields = dict(line.split(':', 1) for line in status if ':' in line)
for name in ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb'):
    assert int(fields[name], 16) == 0, name
assert fields['NoNewPrivs'].strip() == '1'
""", ns(client, "readlink", "/proc/self/ns/net",
        capture_output=True).stdout.strip())
        sandbox_run(socks_probe)
        sandbox_run("""import socket
for address in ('192.0.2.2', '2001:db8::2'):
    for port in (53, 443):
        try:
            with socket.create_connection((address, port), 1):
                raise AssertionError('sandbox direct TCP allowed')
        except OSError:
            pass
""")
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
