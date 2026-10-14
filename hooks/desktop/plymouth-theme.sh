#!/bin/bash
# Install and select the Yaran Plymouth boot splash.
#
# The theme itself lives in assets/plymouth/yaran; the full-screen image is
# the approved "Yaran Emblem" wallpaper, copied in at image build time so the
# repository does not duplicate the PNG.
#
# Selecting the theme here is enough for both targets:
#   * the live image — build.py runs `update-initramfs -u -k all` after all
#     chroot hooks, so the live initramfs picks the theme up;
#   * the installed system — Calamares' initramfs module regenerates the
#     target initramfs from the same /etc/plymouth/plymouthd.conf.
set -euo pipefail

echo 'Installing Yaran Plymouth splash theme'

theme_dir=/usr/share/plymouth/themes/yaran
install -d -m 0755 "$theme_dir"
install -m 0644 /.temp_assets/plymouth/yaran/yaran.plymouth "$theme_dir/yaran.plymouth"
install -m 0644 /.temp_assets/plymouth/yaran/yaran.script "$theme_dir/yaran.script"

background="/usr/share/wallpapers/Yaran Emblem/contents/images/1585x992.png"
if [ ! -f "$background" ]; then
    echo "plymouth-theme: background not found at $background" >&2
    echo "plymouth-theme: run hooks/desktop/plasma-assets.sh before this hook" >&2
    exit 1
fi
install -m 0644 "$background" "$theme_dir/background.png"

set_theme_tool=$(command -v plymouth-set-default-theme || true)
if [ -z "$set_theme_tool" ] && [ -x /usr/sbin/plymouth-set-default-theme ]; then
    set_theme_tool=/usr/sbin/plymouth-set-default-theme
fi
if [ -z "$set_theme_tool" ]; then
    echo 'plymouth-theme: plymouth-set-default-theme is missing' >&2
    exit 1
fi
# Set the default without --rebuild-initrd: the initramfs is regenerated later
# by build.py (live image) or by Calamares on the target, which keeps this hook
# fast and avoids running update-initramfs twice inside the build chroot.
"$set_theme_tool" yaran

# plymouth-set-default-theme writes Theme= into /etc/plymouth/plymouthd.conf;
# that is the single place both initramfs builds read from.
if ! grep -qx 'Theme=yaran' /etc/plymouth/plymouthd.conf; then
    echo 'plymouth-theme: Theme=yaran was not written to plymouthd.conf' >&2
    exit 1
fi

echo 'plymouth-theme: Yaran splash selected as default'
