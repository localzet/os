#!/usr/bin/env python3
"""Verify a signed Localzet ISO checksum without root or network access."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

FINGERPRINT = re.compile(r"(?:[0-9A-F]{40}|[0-9A-F]{64})")
ISO_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.iso")
CHECKSUM = re.compile(rb"([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._-]*\.iso)\n")
REJECT_STATUS = {
    "BADSIG", "ERRSIG", "NO_PUBKEY", "EXPSIG", "EXPKEYSIG", "REVKEYSIG",
    "KEYEXPIRED", "SIGEXPIRED", "NODATA", "FAILURE", "ERROR",
}


def open_regular(path: Path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError(f"Not a regular file: {path}")
        return os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise


def bounded_read(path: Path, limit: int) -> bytes:
    with open_regular(path) as stream:
        data = stream.read(limit + 1)
    if not data or len(data) > limit:
        raise ValueError(f"Empty or oversized verification input: {path}")
    return data


def verify_status(status: str, fingerprint: str) -> None:
    # GPGV validates signatures cryptographically, but trusts every key in
    # its keyring. Separately pin the primary key fingerprint; subkeys may
    # legitimately sign on behalf of that primary key.
    records = [line.split() for line in status.splitlines()
               if line.startswith("[GNUPG:] ")]
    if any(len(row) < 2 or row[1] in REJECT_STATUS for row in records):
        raise ValueError("GPG reported an invalid, expired or revoked signature")
    signatures = [row for row in records if row[1] == "VALIDSIG"]
    if len(signatures) != 1:
        raise ValueError("Expected exactly one valid release signature")
    row = signatures[0]
    # VALIDSIG: signer, date, timestamp, expiry, version, reserved,
    # public-key algo, digest algo, signature class, optional primary key.
    if len(row) not in (11, 12):
        raise ValueError("Unexpected GPG signature status")
    signer = row[2]
    primary = row[11] if len(row) == 12 else signer
    if not FINGERPRINT.fullmatch(signer) or primary != fingerprint:
        raise ValueError("Release signature is not from the pinned primary key")
    if row[9] not in ("8", "9", "10") or row[10] != "00":
        raise ValueError("Expected binary signature with SHA-256/384/512")


def verify(iso: Path, checksum: Path, signature: Path, keyring: Path,
           fingerprint: str) -> str:
    fingerprint = fingerprint.upper()
    if not FINGERPRINT.fullmatch(fingerprint):
        raise ValueError("Provide a full independently trusted key fingerprint")
    if not ISO_NAME.fullmatch(iso.name):
        raise ValueError("Unexpected ISO filename")
    # Copy inputs once into a private temporary directory. Parse the same
    # checksum bytes that were verified; no shell, implicit keyring or URL.
    checksums = bounded_read(checksum, 4096)
    match = CHECKSUM.fullmatch(checksums)
    if match is None or match[2].decode("ascii") != iso.name:
        raise ValueError("Expected exactly one canonical checksum for this ISO")
    with tempfile.TemporaryDirectory(prefix="localzet-release-") as name:
        directory = Path(name)
        manifest = directory / "SHA256SUMS"
        detached = directory / "SHA256SUMS.sig"
        keys = directory / "trusted.gpg"
        manifest.write_bytes(checksums)
        detached.write_bytes(bounded_read(signature, 1024 * 1024))
        keys.write_bytes(bounded_read(keyring, 8 * 1024 * 1024))
        result = subprocess.run(
            ["gpgv", "--homedir", str(directory), "--keyring", str(keys),
             "--status-fd", "1", str(detached), str(manifest)],
            capture_output=True, text=True, check=False, timeout=30,
        )
        if result.returncode:
            raise ValueError("Detached release signature did not verify")
        verify_status(result.stdout, fingerprint)
    with open_regular(iso) as stream:
        before = os.fstat(stream.fileno())
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("ISO changed during verification")
    if digest != match[1].decode("ascii"):
        raise ValueError("ISO SHA-256 does not match the signed checksum")
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iso", type=Path)
    parser.add_argument("--checksum", required=True, type=Path)
    parser.add_argument("--signature", required=True, type=Path)
    parser.add_argument("--keyring", required=True, type=Path,
                        help="Independently obtained binary OpenPGP public keyring")
    parser.add_argument("--fingerprint", required=True,
                        help="Independently trusted full primary key fingerprint")
    args = parser.parse_args()
    try:
        digest = verify(args.iso, args.checksum, args.signature,
                        args.keyring, args.fingerprint)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Verification failed: {exc}\n")
    print(f"Verified signature and SHA-256: {digest}  {args.iso.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
