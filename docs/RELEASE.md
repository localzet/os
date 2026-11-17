# Aurora Complete — release evidence and signed downloads

The CI engineering image is **not** a production release. A checksum provided
with an unsigned archive detects accidental corruption, but cannot establish
who produced the ISO.

## Exact-image acceptance

Record the ISO filename, SHA-256, byte size, build commit, CI run IDs and
archive package versions. Do not substitute the SHA of a later rebuild for
the image actually tested. The unified candidate must pass BIOS/UEFI Live
boot, USB installation, non-target GPT disk preservation, authenticated
installed GNOME, native Files and Control Center, offline document rendering,
Wine, lock screen, and installed-system audit.

Additional production gates remain independent of CI:
- Physical dedicated NVMe/SATA SSD and second-disk EFI/data preservation.
  Use sacrificial drives, current backups and a separate test machine; never
  first-test a destructive installer against a user's only copy of data.
- Secure Boot enabled/disabled, real NVIDIA/AMD/Intel graphics and supported
  NVIDIA driver/CUDA execution, update, reboot and recovery tests.
- Offline install, failed/interrupted update, previous kernel boot, recovery
  from full disk or interrupted package transaction, accessible ru/en UX.
- External services and gaming compatibility with actual authorized accounts
  and applications; document unsupported modes. No synthetic success claims.
- Full installed binary and source package inventory, exact versions and
  license/copyright notices; corresponding sources and redistribution review
  for every included component (including rebuilt GNOME applications and
  bundled ONLYOFFICE). A repository MIT license covers original project code,
  not all third-party packages. Pending proprietary or unreviewed downloads
  are not silently bundled or advertised as ready.
- Release notes, supported hardware/installation boundaries, known issues,
  installation guide, signed downloadable artifacts and update provenance.

Keep the engineering and production channels distinct. Do not turn green
QEMU tests into a production designation or publish a production artifact
automatically from a pull request.

## Package inventory for review

The candidate workflow extracts the embedded package manifest from the actual
ISO and compares it with the prepared rootfs, preserving package versions,
architectures, source package versions and multiplicity. For a local build:

```bash
xorriso -osirrox on -indev localzet-aurora-complete-rc.iso \
    -extract /casper/filesystem.manifest filesystem.manifest
python3 scripts/collect-release-inventory.py /path/to/prepared-rootfs \
    --iso-manifest filesystem.manifest > package-inventory.json
```

Review every entry, retrieve corresponding sources and retain required
notices. The report includes SHA-256 of present copyright files, flags
missing or unsafe notice paths and records redistribution approval as false.
A matching package inventory or present notice does not establish compliance;
the workflow never signs or publishes a production release automatically.

## Signing after acceptance

The release maintainer controls the production OpenPGP signing key offline.
Never create a production key in CI or commit the private key/passphrase.
Publish its full primary fingerprint and public key through an independent,
authenticated channel, with a documented revocation and rotation procedure.
These steps must be performed on the exact accepted ISO:

```bash
# Work in an isolated release staging directory.
sha256sum -- localzet-aurora-complete.iso > SHA256SUMS
gpg --local-user "$RELEASE_PRIMARY_FINGERPRINT" --digest-algo SHA256 \
    --output SHA256SUMS.sig --detach-sign SHA256SUMS
```

Publish the ISO, SHA256SUMS, SHA256SUMS.sig, release documentation, package
inventory and corresponding-source materials. Archive CI evidence separately.
A release must not be re-signed after changing any ISO byte without renewed
acceptance.

## Verify before writing a USB drive

Obtain the public binary keyring and full fingerprint from a previously
trusted source, not merely from the same unverified download. With Python
3.11+ and gpgv installed:

```bash
python3 scripts/verify-release.py localzet-aurora-complete.iso \
    --checksum SHA256SUMS --signature SHA256SUMS.sig \
    --keyring /path/to/trusted-localzet-release.gpg \
    --fingerprint "$TRUSTED_PRIMARY_FINGERPRINT"
```

The verifier accepts exactly one canonical SHA-256 entry for the supplied
ISO basename and exactly one valid binary OpenPGP signature with SHA-256,
SHA-384 or SHA-512, pinned to the trusted primary fingerprint (including a
legitimate signing subkey). It rejects tampering, symlink inputs, unsigned
files, unrelated keys even in the same keyring and weak hashes. It needs
neither root nor network and does not write to any block device.

Use a current trusted keyring including revocation information; the verifier
cannot learn revocations offline or prevent rollback to an older genuine
signed release. Confirm that the version and hash match the intended current
release. A valid signature is not a replacement for hardware acceptance.

No production key, fingerprint, signed ISO or release has been created by
this implementation. CI uses only disposable synthetic keys and data.

### Corresponding source for modified native packages

The Nautilus and Control Center build jobs retain the modified Debian source package (`.dsc` and referenced tarballs) in their engineering evidence under `source/`, alongside SHA-256 checksums and the exact source version. A fresh extraction must reproduce the Localzet patch and changelog version before binary building. This is evidence for the redistribution review, not approval to redistribute the complete image. Preserve these bundles alongside the exact release commit and binary inventory before signing.
