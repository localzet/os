# Native Aurora branding

The revised vector wallpaper is an original restrained violet/ember draft
for the approved Professional direction, not a claim of final art approval.
It ships at 3840 × 2160 with scalable curves; it replaces the old geometric
mountains and is still subject to review in an actual ISO session.

GDM uses the documented `org.gnome.login-screen.logo` key in a dedicated
dconf database ahead of distribution defaults. The build checks the effective
key. It does not alter authentication or disable password requirements.
Capture the real GDM screen after installing and rebooting.

GNOME Shell 50's authenticated unlock dialog creates its screen-shield
`BackgroundManager` without overriding its settings schema. The upstream
`BackgroundManager` default is `org.gnome.desktop.background`, so the lock
shield inherits the user's desktop `picture-uri` / `picture-uri-dark`; the
legacy `org.gnome.desktop.screensaver picture-uri` key is not used by this
GNOME Shell 50 code path. The GDM greeter remains a separate session and reads
`org.gnome.desktop.background` from the dedicated `gdm` dconf profile.

The rootfs configures the user desktop/lock background and GDM greeter
separately. Installed-image acceptance captures the actual locked session and
compares the low-frequency wallpaper structure with the pre-lock desktop
capture, masking the clock, top panel and dock. This catches a flat/default
gradient while allowing GNOME's intentional dim-and-blur effect.

Upstream implementation: [GNOME Shell 50 unlockDialog.js](https://github.com/GNOME/gnome-shell/blob/50.0/js/ui/unlockDialog.js)
and [background.js](https://github.com/GNOME/gnome-shell/blob/50.0/js/ui/background.js).

The OS exposes `LOGO=localzet-logo` and packages the original logo in hicolor.
GNOME Control Center 50 upstream reads LOGO **only if** distributor-logo
build options are absent. Ubuntu may compile absolute logo paths; the
os-release change alone does not establish that About shows Localzet.
For the supported unified settings build, rebuild Ubuntu's source package
with meson `distributor_logo` and `dark_mode_distributor_logo` pointing to
`/usr/share/localzet/brand/localzet.svg`, or remove those flags and use
the upstream LOGO lookup. Preserve all other Ubuntu patches/dependencies,
track exact upstream security versions and build provenance. No overwrite
of files owned by Ubuntu packages, no binary patching, no dpkg-divert hack.
Verify the actual About screen and subsequent settings panels.

Sources:
- https://help.gnome.org/system-admin-guide/login-logo.html
- https://github.com/GNOME/gnome-control-center/blob/50.0/panels/system/about/cc-about-page.c
- https://github.com/GNOME/gnome-control-center/blob/50.0/meson.build
