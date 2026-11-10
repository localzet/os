# Security constraints

- Never elevate privileges from GNOME Shell JS. User interfaces call scoped system APIs.
- The module catalogue is **data**: do not execute scripts, arbitrary APT arguments, URLs, or shell commands from a manifest.
- Installation/update/uninstallation will require verified package sources, polkit permissions, explicit change previews, transactional logging, rollback and safe recovery.
- Never silently remove Docker volumes, images, Wine prefixes or user data.
- Do not auto-enable host-wide TUN/proxy or change routing without meaningful consent, rollback and tests.
- Verify upstream package names and licensing before bundling proprietary apps such as Microsoft Edge or Steam.
- No distribution signatures, Secure Boot integration, encryption or ISO boot validation are implemented in P0.
