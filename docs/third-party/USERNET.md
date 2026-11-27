# UserNet Linux package provenance

**Status: engineering-only; not approved for redistribution in an Aurora ISO.**

- Upstream project: [localzet/UserNet](https://github.com/localzet/UserNet)
- Source tag: `v0.5.12`
- Tag commit: `7f3e199846bffdfac58434640d009493fcc4c566`
- Source version: `0.5.12+2026110805`
- Debian package version: `0.5.12.2026110805`
- Declared license: GPL-3.0; the tagged source contains `LICENSE`.

The version and source tag are pinned, but the upstream release workflow downloads the Linux DEB from `updates.userlay.com/linux/stable.json`; it does not build that DEB from the tagged source in the same workflow. Therefore the exact binary-to-source build mapping is not established. The current DEB also lacks `/usr/share/doc/usernet/copyright`, and bundled Flutter/Go/Rust dependency notices have not yet been audited.

The package may be installed and tested in disposable engineering images. It must not be included in a published ISO until the build mapping, complete notices, license review and redistribution approval are verified. The unified RC workflow checks these conditions and fails closed.
