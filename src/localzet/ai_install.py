"""Explicit user-local installation of reviewed official AI CLI binaries."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile

CODEX_VERSION = "0.170.0"
CODEX_ASSET = "codex-x86_64-unknown-linux-musl.tar.gz"
CLAUDE_ROOT = "https://downloads.claude.ai/claude-code-releases"
CLAUDE_KEY = "https://downloads.claude.ai/keys/claude-code.asc"
FINGERPRINT = "31DDDE24DDFAB679F42D7BD2BAA929FF1A7E"
MAX_BINARY = 512 * 1024**2
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
DIGEST = re.compile(r"[a-f0-9]{64}")


def download(url, output, limit, proxy):
    # Fixed vendor URLs only; no inherited curlrc, no insecure redirects.
    command = ["/usr/bin/curl", "-q", "--fail", "--silent", "--show-error",
               "--location", "--proto", "=https", "--proto-redir", "=https",
               "--connect-timeout", "20", "--max-time", "240",
               "--max-filesize", str(limit), "--output", str(output)]
    if proxy:
        command += ["--proxy", proxy, "--noproxy", ""]
    else:
        # Only disposable CI review uses this mode.
        command += ["--proxy", "", "--noproxy", "*"]
    subprocess.run([*command, url], check=True, timeout=250)
    if not output.is_file() or not 0 < output.stat().st_size <= limit:
        raise ValueError("Unexpected download size")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(path, expected):
    if not isinstance(expected, str) or not DIGEST.fullmatch(expected) or digest(path) != expected:
        raise ValueError("SHA-256 mismatch")


def codex_metadata(data):
    if data.get("tag_name") != "rust-v" + CODEX_VERSION or data.get("draft") or data.get("prerelease"):
        raise ValueError("Unexpected Codex release")
    matches = [a for a in data["assets"] if a["name"] == CODEX_ASSET]
    if len(matches) != 1:
        raise ValueError("Missing exact Codex asset")
    item = matches[0]
    url = "https://github.com/openai/codex/releases/download/rust-v" + CODEX_VERSION + "/" + CODEX_ASSET
    if item["browser_download_url"] != url or type(item["size"]) is not int or not 0 < item["size"] <= MAX_BINARY:
        raise ValueError("Invalid Codex asset metadata")
    raw_digest = item.get("digest")
    if not isinstance(raw_digest, str):
        raise ValueError("Codex release digest absent")
    checksum = raw_digest.removeprefix("sha256:")
    if not item["digest"].startswith("sha256:") or not DIGEST.fullmatch(checksum):
        raise ValueError("Codex release digest absent")
    return url, item["size"], checksum


def unpack_codex(archive, output):
    with tarfile.open(archive, "r:gz") as tar:
        entries = list(tar)
        expected = CODEX_ASSET.removesuffix(".tar.gz")
        if len(entries) != 1 or entries[0].name not in (expected, "./" + expected):
            raise ValueError("Unexpected Codex archive contents")
        member = entries[0]
        if not member.isfile() or not 0 < member.size <= MAX_BINARY:
            raise ValueError("Unexpected Codex archive member")
        with tar.extractfile(member) as source, output.open("xb") as destination:
            shutil.copyfileobj(source, destination)
    if output.stat().st_size != member.size:
        raise ValueError("Truncated Codex executable")


def claude_version(value):
    value = value.strip()
    if not VERSION.fullmatch(value):
        raise ValueError("Unexpected Claude stable channel version")
    return value


def verify_manifest(directory):
    key = directory / "claude-code.asc"
    gnupg = directory / "gnupg"
    gnupg.mkdir(mode=0o700)
    command = ["/usr/bin/gpg", "--batch", "--no-options", "--homedir", str(gnupg)]
    out = subprocess.check_output([*command, "--with-colons", "--show-keys", str(key)], text=True, timeout=30)
    primaries = []
    primary = False
    for line in out.splitlines():
        fields = line.split(":")
        if fields[0] == "pub":
            primary = True
        elif fields[0] == "sub":
            primary = False
        elif fields[0] == "fpr" and primary:
            primaries.append(fields[9])
            primary = False
    if primaries != [FINGERPRINT]:
        raise ValueError("Unexpected Anthropic signing key")
    subprocess.run([*command, "--import", str(key)], check=True, timeout=30)
    result = subprocess.run([*command, "--status-fd", "1", "--verify",
                             str(directory / "manifest.json.sig"), str(directory / "manifest.json")],
                            text=True, capture_output=True, check=True, timeout=30)
    valid = [line.split() for line in result.stdout.splitlines() if line.startswith("[GNUPG:] VALIDSIG ")]
    if len(valid) != 1 or valid[0][-1] != FINGERPRINT:
        raise ValueError("Manifest signer does not match pinned primary key")


def prepare(tool, directory, proxy):
    binary = directory / tool
    if tool == "codex":
        meta = directory / "release.json"
        download("https://api.github.com/repos/openai/codex/releases/tags/rust-v" + CODEX_VERSION, meta, 4*1024**2, proxy)
        url, size, checksum = codex_metadata(json.loads(meta.read_text()))
        archive = directory / CODEX_ASSET
        download(url, archive, size, proxy)
        if archive.stat().st_size != size:
            raise ValueError("Codex release size mismatch")
        verify(archive, checksum)
        unpack_codex(archive, binary)
        version = CODEX_VERSION
        evidence = {"source": url, "archive_sha256": checksum, "verification": "github-release-digest"}
    elif tool == "claude":
        stable = directory / "stable"
        download(CLAUDE_ROOT + "/stable", stable, 1024, proxy)
        version = claude_version(stable.read_text())
        root = CLAUDE_ROOT + "/" + version
        for name, url, limit in (("claude-code.asc", CLAUDE_KEY, 128*1024),
                                 ("manifest.json", root + "/manifest.json", 1024**2),
                                 ("manifest.json.sig", root + "/manifest.json.sig", 128*1024)):
            download(url, directory / name, limit, proxy)
        verify_manifest(directory)
        manifest = json.loads((directory / "manifest.json").read_text())
        if manifest.get("version") != version:
            raise ValueError("Claude manifest version mismatch")
        checksum = manifest["platforms"]["linux-x64"]["checksum"]
        url = root + "/linux-x64/claude"
        download(url, binary, MAX_BINARY, proxy)
        verify(binary, checksum)
        evidence = {"source": url, "signer": FINGERPRINT, "verification": "signed-manifest"}
    else:
        raise ValueError("Unknown AI client")
    with binary.open("rb") as stream:
        magic = stream.read(4)
    if magic != b"\x7fELF":
        raise ValueError("Expected Linux executable")
    binary.chmod(0o700)
    return binary, {"tool": tool, "version": version, "sha256": digest(binary), **evidence}


def private(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise ValueError("Client directory must be user-owned and not writable by others")


def publish(binary, receipt, root):
    if not VERSION.fullmatch(receipt["version"]):
        raise ValueError("Invalid version")
    private(root)
    target = root / receipt["version"]
    if receipt.get("tool") not in ("codex", "claude"):
        raise ValueError("Invalid tool")
    if target.exists() or target.is_symlink():
        private(target)
        verify(target / receipt["tool"], receipt["sha256"])
    else:
        with tempfile.TemporaryDirectory(prefix=".install-", dir=root) as stage:
            staging = Path(stage)
            shutil.copy2(binary, staging / receipt["tool"])
            (staging / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
            staging.rename(target)
    with tempfile.TemporaryDirectory(prefix=".link-", dir=root) as tmp:
        link = Path(tmp) / "current"
        link.symlink_to(Path(receipt["version"]) / receipt["tool"])
        current = root / "current"
        if current.exists() and not current.is_symlink():
            raise ValueError("Refusing to replace non-managed current file")
        os.replace(link, current)
    return current


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", choices=("codex", "claude"))
    parser.add_argument("--review-dir", type=Path, help="Disposable CI only; download evidence without installing")
    args = parser.parse_args()
    if os.geteuid() == 0 or platform.machine() != "x86_64":
        parser.exit(2, "Requires a non-root x86-64 Linux user\n")
    try:
        if args.review_dir:
            if os.environ.get("LOCALZET_DISPOSABLE_VM") != "1":
                raise ValueError("Review mode is for disposable CI only")
            args.review_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
            _, receipt = prepare(args.tool, args.review_dir, None)
            (args.review_dir / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
            print(json.dumps(receipt, indent=2))
            return 0
        if "boot=casper" in Path("/proc/cmdline").read_text().split():
            raise ValueError("Install Localzet OS first")
        if not os.isatty(0):
            raise ValueError("Interactive confirmation required")
        from localzet.ai_network import usernet_port
        proxy = "http://127.0.0.1:" + str(usernet_port())
        print("Download via configured local HTTP proxy. No direct fallback.")
        if input("Download and verify official client? [y/N] ").strip().lower() != "y":
            return 1
        with tempfile.TemporaryDirectory(prefix="localzet-ai-install-") as tmp:
            binary, receipt = prepare(args.tool, Path(tmp), proxy)
            print(json.dumps(receipt, indent=2))
            if input("Install this exact version for your user? [y/N] ").strip().lower() != "y":
                return 1
            root = Path.home() / ".local/share/localzet/ai-clients" / args.tool
            print("Installed:", publish(binary, receipt, root))
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, subprocess.SubprocessError) as error:
        parser.exit(2, f"Localzet AI install: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
