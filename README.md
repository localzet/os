# Localzet OS

A modular Ubuntu-based desktop distribution with a consistent GNOME interface.

**Status: P1 experimental Live ISO construction (boot and installer NOT yet verified).**

## Target

- Ubuntu **26.04 LTS** (Resolute Raccoon), GNOME **50**, Wayland.
- Cohesive Localzet design system, shell and system applications.
- Optional install-on-demand components for containers, gaming, private networking and development.
- Windows application support via Wine/Proton with documented compatibility limitations.
- Least-privilege system integration, safe upgrades and recovery.

## What's actually in this repository?

1. A small GNOME Shell 50 extension adding a Localzet menu to the top panel. **It has not been run against a real GNOME 50 session yet.**
2. An original SVG wallpaper and draft design tokens.
3. A standard-library Python **read-only** module planner: validates manifests and prints dependency-ordered plans without installing anything.
4. Automated unit tests and source validation in GitHub Actions.
5. Explicit architecture decisions, migration notes, and acceptance criteria.

## Try it safely

On a disposable **Ubuntu 26.04 VM** (not a production workstation):

```bash
make test
PYTHONPATH=src python3 -m localzet.cli list
PYTHONPATH=src python3 -m localzet.cli plan containers
bash scripts/install-shell-dev.sh
# Log out and back in, then enable the extension from GNOME Extensions.
```

The shell installer only copies a folder into the current user's home directory; it does not use sudo or change package sources. To remove it, see [docs/BUILD.md](docs/BUILD.md).

## Important boundaries

- The first experimental Live ISO builder is in [docs/LIVE-ISO.md](docs/LIVE-ISO.md). A valid, bootable artifact is **not confirmed** until CI and QEMU tests pass. The installer, custom package repository, signed updates, privileged module activation and hardware support are future work.
- `plan` is deliberately read-only. It never executes APT or systemd.
- Ubuntu, GNOME, Microsoft Edge, Steam, Docker, NetBird, Wine and other names belong to their respective owners and retain their own license terms.
- The upstream project's existing code and history remain at [localzet/localzet-os](https://github.com/localzet/localzet-os). See [migration](docs/MIGRATION.md).

## Development

```bash
make test
make extension-zip  # requires the gnome-extensions CLI
```

Read [architecture](docs/ARCHITECTURE.md), [roadmap](docs/ROADMAP.md), [build notes](docs/BUILD.md) [GNOME 50 smoke-test instructions](docs/GNOME-50-SMOKE.md) and [security](docs/SECURITY.md) before shipping anything.
