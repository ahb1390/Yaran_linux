#!/bin/bash
# Install the branded GRUB theme into the image so the INSTALLED system gets
# the same visual identity as the live ISO. The live ISO menu is generated
# separately by build.py (grub_menu.background); this hook only prepares the
# on-disk theme, and `update-grub` — run by Calamares' bootloader module on the
# target — wires it up through GRUB_THEME (see hooks/desktop/login-branding.sh).
set -euo pipefail

theme_dir=/usr/share/grub/themes/yaran
echo 'Installing Yaran GRUB theme for the installed system'

install -d -m 0755 "$theme_dir/fonts"
install -m 0644 /.temp_assets/grub-theme/yaran/theme.txt "$theme_dir/theme.txt"

background="/usr/share/wallpapers/Yaran Emblem/contents/images/1585x992.png"
if [ ! -f "$background" ]; then
    echo "grub-theme: wallpaper background not found at $background" >&2
    echo "grub-theme: run hooks/desktop/plasma-assets.sh before this hook" >&2
    exit 1
fi
install -m 0644 "$background" "$theme_dir/background.png"

# Build the theme fonts from DejaVu Sans and DejaVu Sans Mono (both shipped
# by fonts-dejavu-core, part of the Debian "important" priority set).
# theme.txt references each family by name, so BOTH .pf2 files must exist:
# GRUB cannot silently substitute one theme font for another. If the Mono
# face is missing the theme is rewritten to the regular face, and if DejaVu
# is unavailable entirely, GRUB's bundled Unifont is installed under both
# names so every reference in theme.txt still resolves.
dejavu_dir=/usr/share/fonts/truetype/dejavu
if command -v grub-mkfont >/dev/null 2>&1 && [ -f "$dejavu_dir/DejaVuSans.ttf" ]; then
    grub-mkfont --output="$theme_dir/fonts/DejaVuSans.pf2" "$dejavu_dir/DejaVuSans.ttf"
    echo "grub-theme: generated DejaVu Sans font"
    if [ -f "$dejavu_dir/DejaVuSansMono.ttf" ]; then
        grub-mkfont --output="$theme_dir/fonts/DejaVuSansMono.pf2" "$dejavu_dir/DejaVuSansMono.ttf"
        echo "grub-theme: generated DejaVu Sans Mono font"
    else
        echo "grub-theme: DejaVuSansMono.ttf missing; theme falls back to the regular face"
        sed -i 's/DejaVu Sans Mono/DejaVu Sans/' "$theme_dir/theme.txt"
    fi
elif [ -f /usr/share/grub/unicode.pf2 ]; then
    echo "grub-theme: grub-mkfont or DejaVu missing; using bundled Unifont"
    install -m 0644 /usr/share/grub/unicode.pf2 "$theme_dir/fonts/DejaVuSans.pf2"
    install -m 0644 /usr/share/grub/unicode.pf2 "$theme_dir/fonts/DejaVuSansMono.pf2"
    sed -i 's/DejaVu Sans Mono/Unifont/; s/DejaVu Sans/Unifont/' "$theme_dir/theme.txt"
else
    echo 'grub-theme: no GRUB font available to build the theme' >&2
    exit 1
fi

echo "grub-theme: installed to $theme_dir"
