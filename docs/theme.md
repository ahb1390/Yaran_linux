# Yaran Linux Theme Guide

This document describes the visual identity of Yaran Linux and where each part
of it lives, so future changes stay coherent.

## Design language: "emerald terminal"

One quiet idea: **a very dark green screen with a single emerald glow.** Every
themed surface (boot splash, login, session accents, installer) uses the same
palette, the same typography rules, and restrained motion. Nothing bounces,
nothing blinks fast, nothing competes with the logo. Neon green appears only as
a small accent — focus rings, progress lines, the logo mark — never as a large
filled surface.

The logo itself (`yaran.svg`) keeps a single shared identity: a dark forest
tile with a geometric emerald `Y`. The same artwork is used by the standalone
logo, the Calamares installer branding, and the Plasma application icon.

## Palette

| Token | Hex | Used for |
|---|---|---|
| `bg` | `#07110F` | Splash and greeter background, window background |
| `surface` | `#0B2E22` | Titlebar, sidebar, elevated surfaces |
| `card` | `#0A1914` | Greeter login card |
| `field` | `#0E241C` | Input fields and buttons |
| `field-border` | `#1E4436` | Unfocused field border |
| `brand` | `#087F4F` | Selection highlight, titlebar blend, accent color |
| `glow` | `#20D878` | Logo mark, focus ring, progress line, hover accents |
| `ink` | `#E7F5EC` | Primary text |
| `muted` | `#9DBFAC` | Secondary labels and hints |

Rules of thumb: emerald is the only saturated color on themed screens;
`#39FF88` (neon green) is reserved for rare, tiny accents and is not part of
the daily UI; white appears only as low-opacity structure (dividers, track
lines); never introduce a second hue.

## Typography

Noto Sans is the primary font for the Plasma session, SDDM login, boot splash,
and installer. Noto Sans Mono is used for fixed-width text. Wordmarks use large
letter-spacing (4–6) and no bold weight. Labels are small (9 pt) with
letter-spacing 1 and reduced opacity instead of grey colors.

## Motion

- Durations: 200–900 ms, `OutCubic` for movement, `InOutSine` for opacity loops.
- One animated element at a time; loops must be slow (≥ 1.4 s per cycle).
- The splash progress line is tied to real ksplash stages — never fake
  progress.

## Components and file locations

All paths are relative to `assets/yaran-plasma-theme/`.

| Screen | File |
|---|---|
| Boot splash | `usr/share/plasma/look-and-feel/org.yaranlinux.desktop/contents/splash/Splash.qml` |
| Login (SDDM greeter) | `usr/share/sddm/themes/yaran-greeter/Main.qml` |
| SDDM theme registration | `usr/share/sddm/themes/yaran-greeter/metadata.desktop` |
| SDDM wallpaper | `usr/share/sddm/themes/yaran-greeter/theme.conf` |
| SDDM selection | `etc/sddm.conf.d/yaran.conf` (`Current=yaran-greeter`) |
| Session color scheme | `etc/xdg/kdeglobals` |
| Full color scheme | `usr/share/color-schemes/yaran-emerald.colors` |
| Default wallpaper | `../../wallpapers/Yaran Emblem/` (installed to `/usr/share/wallpapers/`) |

The default wallpaper package is referenced from three places that must stay in
sync: the look-and-feel `contents/defaults` (`[Wallpaper] Image=`), the layout
template's `contents/layout.js`, and the SDDM `theme.conf`.

The SDDM greeter is installed by `hooks/desktop/plasma-assets.sh`; the
`etc/` defaults by `hooks/desktop/desktop-defaults.sh`. If you add files
under a new `usr/share/` subdirectory, make sure a hook copies it.

## Logout / shutdown

Plasma 6 does not allow the logout confirmation dialog to be themed through
the look-and-feel package. The stock dialog is kept on purpose; continuity
comes from the shared dark palette, not a custom dialog. Do not ship a
custom `contents/logout/Logout.qml` — it risks breaking logout on Plasma
updates.

## Changing the theme

- Keep new colors out; extend the table above only if a token is genuinely
  missing.
- Test any QML change by booting the live ISO in a VM: splash, login
  (wrong password included), and a normal session login.
