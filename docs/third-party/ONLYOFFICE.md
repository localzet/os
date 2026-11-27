# ONLYOFFICE Desktop Editors 10.0.0 — provenance and distribution gate

Status: **engineering-only; redistribution is blocked pending source/build provenance**.

## Pinned binary

- Official release: https://github.com/ONLYOFFICE/DesktopEditors/releases/tag/v10.0.0
- Debian package: `onlyoffice-desktopeditors_amd64.deb`, version `10.0.0-169`
- Size: `279357060` bytes
- SHA-256: `2190edb4022a2ac2f6eee0f78815520f0e4ece1e8a1097c645a6f9b225c8b59c`
- The digest was returned by the GitHub Releases API. It is a useful exact-byte pin, **not an independent publisher signature**.

The installed package was inspected in a disposable rootfs. Its control archive contains only `postrm`; the purge path removes user preferences/data, so Localzet never purges it automatically. The reviewed dependency transaction does not install Microsoft core fonts or accept a font EULA.

## Source reconstruction currently available

The current public tag resolves to:

- DesktopEditors commit: `daf8c6948148827201b2907ac1134d222fbfa7b4`
- Tree: `1fa56830c7fc158f3772c5507c3124fb401d080a`
- Tag commit date: 2026-10-22 17:54:33 UTC
- Release publication date: 2026-10-13 10:18:58 UTC
- GitHub reports the tag commit as **unsigned**.

The tag's pinned submodules are recorded in `config/upstream/onlyoffice.json`:

| Path | Repository | Pinned commit |
|---|---|---|
| `core` | [ONLYOFFICE/core](https://github.com/ONLYOFFICE/core) | `ed63e94de814ff1d4ea28cddfaba6939bc9df9ed` |
| `desktop-apps` | [ONLYOFFICE/desktop-apps](https://github.com/ONLYOFFICE/desktop-apps) | `332c1905a5361dd4139481827b7ad4f4a9facd85` |
| `desktop-sdk` | [ONLYOFFICE/desktop-sdk](https://github.com/ONLYOFFICE/desktop-sdk) | `ae6cf2a039355183c512fc314f7a9bd1a05a6a11` |
| `dictionaries` | [ONLYOFFICE/dictionaries](https://github.com/ONLYOFFICE/dictionaries) | `d3223bbb777883db66ac3cd249f71c6ebdc992c7` |
| `sdkjs` | [ONLYOFFICE/sdkjs](https://github.com/ONLYOFFICE/sdkjs) | `9d2138866d929be32f1d107e8b5bfae36156e097` |
| `web-apps` | [ONLYOFFICE/web-apps](https://github.com/ONLYOFFICE/web-apps) | `f79972a400c3a696490094961772d1f86fac1b82` |

A source tree can be reconstructed for the *current tag* with:

```sh
git clone https://github.com/ONLYOFFICE/DesktopEditors.git
git -C DesktopEditors checkout daf8c6948148827201b2907ac1134d222fbfa7b4
git -C DesktopEditors submodule update --init --recursive
```

This does **not** prove that this source tree produced the October 13 binary. The current tag and submodule commits post-date the release publication, the tag and observed submodule commits are unsigned, and the release metadata does not identify a build commit. Therefore the exact corresponding source for the pinned DEB remains unverified. Do not describe the current tag as the binary's corresponding source.

## License and notices

The installed package declares:

- Program: **AGPL-3.0-only**
- Bundled image assets: **CC-BY-SA-4.0**
- Copyright: Ascensio System SIA, 2009–2026

Preserve the vendor `LICENSE.txt` and Debian copyright notice. The package installs them at:

- `/opt/onlyoffice/desktopeditors/LICENSE.txt`
- `/usr/share/doc/onlyoffice-desktopeditors/copyright`

These files are captured by the installed-image review workflow.

## Updates

The candidate uses a pinned GitHub release asset; no ONLYOFFICE APT source is configured and automatic updates are not enabled. The official Desktop Editors instructions document `https://download.onlyoffice.com/repo/debian squeeze main` and key ID `CB2DE8E5` ([official instructions](https://helpcenter.onlyoffice.com/desktop/installation/linux-version/desktop-install-ubuntu)), but the full key fingerprint has not yet been independently verified. Do not configure that repository or weaken APT authentication until the full fingerprint and signed repository metadata are checked.

## Release gate

Before public ISO distribution, obtain upstream confirmation of the exact source/build commit for this DEB (including all submodules), or switch to an authenticated package channel with a verified full key fingerprint and source correspondence. Then verify license notices and a supported update path. Until then this package remains an engineering-only, pinned dependency.


## CI artifact enforcement

The repository is public, so a GitHub Actions artifact is accessible to readers of the repository. While the corresponding source/build mapping is unverified, the Complete RC workflow may assemble, boot and install this image only inside disposable CI. It must not upload the ISO. It may upload test logs, screenshots, package inventory, licensing evidence and the exact ISO checksum without the binary. The workflow enables the ISO artifact only when the manifest records verified corresponding source, redistribution status and a supported update channel.
