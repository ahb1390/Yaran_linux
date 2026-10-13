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

background=/usr/share/wallpapers/Yaran Emblem/contents/images/1585x992.png
if [ ! -f "$background" ]; then
    echo "grub-theme: wallpaper background not found at $background" >&2
    echo "grub-theme: run hooks/desktop/plasma-assets.sh before this hook" >&2
    exit 1
fi
install -m 0644 "$background" "$theme_dir/background.png"

# Build the theme font from DejaVu Sans (shipped by fonts-dejavu-core, part of
# the Debian "important" priority set). Fall back to GRUB's bundled Unifont on
# systems where either tool is missing, rewriting the theme so it references
# the font that actually exists.
if command -v grub-mkfont >/dev/null 2>&1 && [ -f /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf ]; then
    grub-mkfont --output="$theme_dir/fonts/DejaVuSans.pf2" \
        /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
    echo "grub-theme: generated DejaVu Sans font"
elif [ -f /usr/share/grub/unicode.pf2 ]; then
    echo "grub-theme: grub-mkfont or DejaVu missing; using bundled Unifont"
    install -m 0644 /usr/share/grub/unicode.pf2 "$theme_dir/fonts/DejaVuSans.pf2"
    sed -i 's/DejaVu Sans Mono/Unifont/; s/DejaVu Sans/Unifont/' "$theme_dir/theme.txt"
else
    echo 'grub-theme: no GRUB font available to build the theme' >&2
    exit 1
fi

echo "grub-theme: installed to $theme_dir"
