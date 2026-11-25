#!/usr/bin/env python3
"""Read back Aurora settings inside the live user's graphical session."""
import argparse
import ast
import subprocess


THEMES = {
    "blue": {
        "appearance": "blue",
        "wallpaper": "aurora-blue",
        "wallpaper_dark": "aurora-blue",
        "icons": "Localzet",
        "accent": "blue",
        "gtk_theme": "Localzet-Aurora-Blue",
    },
    "purple": {
        "appearance": "purple",
        "wallpaper": "aurora-purple",
        "wallpaper_dark": "aurora-purple",
        "icons": "Localzet",
        "accent": "purple",
        "gtk_theme": "Localzet-Aurora-Purple",
    },
    "black": {
        "appearance": "black",
        "wallpaper": "aurora-black",
        "wallpaper_dark": "aurora-black",
        "icons": "Localzet",
        "accent": "purple",
        "gtk_theme": "Localzet-Aurora-Black",
    },
    "restore": {
        "appearance": "purple",
        "wallpaper": "aurora-black",
        "wallpaper_dark": "aurora-black",
        "icons": "Adwaita",
        "accent": "blue",
        "gtk_theme": "Yaru-dark",
    },
}


SETTINGS = {
    "appearance": ("com.localzet.shell", "appearance"),
    "wallpaper": ("org.gnome.desktop.background", "picture-uri"),
    "wallpaper_dark": ("org.gnome.desktop.background", "picture-uri-dark"),
    "icons": ("org.gnome.desktop.interface", "icon-theme"),
    "accent": ("org.gnome.desktop.interface", "accent-color"),
    "gtk_theme": ("org.gnome.desktop.interface", "gtk-theme"),
}


def read_setting(schema: str, key: str):
    result = subprocess.run(
        ["gsettings", "get", schema, key],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return ast.literal_eval(result.stdout.strip())


def verify(profile: str) -> int:
    expected = THEMES[profile]
    actual = {}
    for name, (schema, key) in SETTINGS.items():
        try:
            actual[name] = read_setting(schema, key)
        except (OSError, subprocess.SubprocessError, ValueError, SyntaxError) as error:
            print(f"LOCALZET_APPEARANCE_VERIFY=FAIL {name}: {error}", flush=True)
            return 1

    wallpaper_names = {
        name: actual[name].rsplit("/", 1)[-1].removesuffix(".webp")
        for name in ("wallpaper", "wallpaper_dark")
    }
    checks = {
        "appearance": actual["appearance"] == expected["appearance"],
        "wallpaper": all(
            wallpaper == expected["wallpaper"]
            for wallpaper in wallpaper_names.values()
        ),
        "icons": actual["icons"] == expected["icons"],
        "accent": actual["accent"] == expected["accent"],
        "gtk_theme": actual["gtk_theme"] == expected["gtk_theme"],
    }
    if not all(checks.values()):
        print(f"LOCALZET_APPEARANCE_VERIFY=FAIL {actual}", flush=True)
        return 1

    print(
        "PASS Aurora profile "
        f"{expected['appearance']} wallpaper {expected['wallpaper']} "
        f"icons {expected['icons']} accent {expected['accent']}",
        flush=True,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=tuple(THEMES))
    args = parser.parse_args()
    return verify(args.profile)


if __name__ == "__main__":
    raise SystemExit(main())
