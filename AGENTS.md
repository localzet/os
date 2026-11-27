# Localzet OS engineering notes

- Communicate in Russian. Code comments are brief English and explain only
  non-obvious constraints.
- This repository is the canonical implementation target. Keep design
  reference archives read-only and port only reviewed first-party assets.
- Target Ubuntu 26.04 LTS, GNOME 50 and Wayland. Treat Chromium previews as
  design references, never as GNOME runtime evidence.
- Aurora Blue is the default. Blue, Purple and Black retain the approved
  palette in `assets/design-tokens.json`; do not replace it with a new scheme.
- Theme selection belongs in Settings → Appearance, never in the top bar.
  Appearance changes must remain user-scoped, preserve an explicit restore
  point, and work safely when Localzet Shell or User Themes is unavailable.
- Use the installed upstream icon for third-party applications. Do not draw
  or bundle third-party logos; use Adwaita/hicolor fallback for uncovered
  names.
- Keep mocks and unimplemented backends clearly identified. Do not report a
  GNOME, ISO, scaling, accessibility or screenshot gate as passed without
  observable evidence and recorded provenance.
- Preserve user changes. For behavior changes, add regression coverage and run
  the narrowest relevant checks before reporting completion.
