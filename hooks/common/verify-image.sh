#!/bin/bash
# Final in-image consistency checks, run as the last chroot hook so a build
# fails loudly if the produced root filesystem violates the policies below.
# This inspects the ACTUAL rootfs that ends up inside the squashfs, not just
# the repository files.
#
# Desktop-only checks run only when a Plasma session is present, so the same
# hook can be reused by any manifest.
set -euo pipefail

fail=0
problem() { echo "verify-image: FAIL: $*" >&2; fail=1; }
ok() { echo "verify-image: ok: $*"; }

is_desktop() { [ -e /usr/bin/plasmashell ]; }

# --- 1. APT sources hygiene -------------------------------------------------
# No repository may bypass signature verification, and anything that is not a
# plain Debian repository must pin its origin with signed-by=<keyring>.
while IFS= read -r file; do
    while IFS= read -r line; do
        case "$line" in
            deb\ *|deb-src\ *)
                case "$line" in
                    *trusted=yes*|*trusted=\**|*check-valid-until=no*)
                        problem "insecure option in $file: $line"
                        ;;
                esac
                case "$line" in
                    *deb.debian.org*|*security.debian.org*) : ;;
                    *signed-by=*) : ;;
                    \#*) : ;;
                    *) problem "non-Debian source without signed-by in $file: $line" ;;
                esac
                ;;
        esac
    done < "$file"
done < <(find /etc/apt -maxdepth 2 -type f \( -name '*.list' -o -name 'sources.list' \) -print)
[ "$fail" -eq 0 ] && ok 'APT sources are signed and minimal'

# If trixie-backports is enabled there must be a pin proving it is required.
if grep -Rqs 'trixie-backports' /etc/apt/ 2>/dev/null; then
    if ! grep -Rqs 'Pin: release n=trixie-backports' /etc/apt/preferences.d/ 2>/dev/null; then
        problem 'trixie-backports enabled without a package pin justifying it'
    else
        ok 'trixie-backports present with an explicit package pin'
    fi
fi

# --- 2. Desktop: no background APT locks -----------------------------------
if is_desktop; then
    if grep -Eq 'APT::Periodic::(Update-Package-Lists|Unattended-Upgrade) "1"' \
        /etc/apt/apt.conf.d/20auto-upgrades 2>/dev/null; then
        problem 'automatic APT updates are enabled in 20auto-upgrades'
    else
        ok 'automatic APT updates disabled (user-initiated via yaran-update)'
    fi
    for unit in apt-daily.timer apt-daily-upgrade.timer unattended-upgrades.service; do
        state=$(systemctl is-enabled "$unit" 2>/dev/null || true)
        case "$state" in
            enabled|static|indirect) problem "$unit is $state and can take the APT lock" ;;
        esac
    done
    [ "$fail" -eq 0 ] && ok 'no background unit can take the APT/DPKG locks'
    test -x /usr/local/bin/yaran-update || problem 'yaran-update helper missing'
fi

# --- 3. Desktop: screen-sharing stack --------------------------------------
if is_desktop; then
    for pkg in xdg-desktop-portal xdg-desktop-portal-kde pipewire pipewire-audio wireplumber; do
        dpkg -s "$pkg" >/dev/null 2>&1 || problem "missing package required for screen sharing: $pkg"
    done
    [ "$fail" -eq 0 ] && ok 'portal + PipeWire screen-sharing stack installed'
fi

# --- 4. Desktop: font coverage ---------------------------------------------
if is_desktop; then
    for pkg in fonts-vazirmatn fonts-vazirmatn-variable fonts-noto-cjk fonts-noto-color-emoji; do
        dpkg -s "$pkg" >/dev/null 2>&1 || problem "missing font package: $pkg"
    done
    test -f /etc/fonts/conf.d/99-yaran-default-fonts.conf || \
        problem 'Yaran fontconfig defaults missing'
    fc-list :lang=zh family 2>/dev/null | grep -q 'Noto Sans CJK' || \
        problem 'no CJK font registered in fontconfig'
    fc-list :lang=fa family 2>/dev/null | grep -q 'Vazirmatn' || \
        problem 'no Persian font registered in fontconfig'
    [ "$fail" -eq 0 ] && ok 'fa/ar/cjk/emoji fonts installed and registered'
fi

# --- 5. Desktop: skel and wallet policy ------------------------------------
if is_desktop; then
    test -d /etc/skel/Projects || problem '/etc/skel/Projects is missing'
    grep -A2 '^\[Wallet\]' /etc/xdg/kdeglobals 2>/dev/null | grep -q 'Enabled=false' || \
        problem 'KWallet is not disabled in /etc/xdg/kdeglobals'
    [ "$fail" -eq 0 ] && ok 'skel Projects folder present; KWallet disabled'
fi

# --- 6. Desktop: boot branding ---------------------------------------------
if is_desktop; then
    grub_theme=$(sed -n 's/^GRUB_THEME="\(.*\)"/\1/p' /etc/default/grub.d/50-yaran.cfg 2>/dev/null || true)
    if [ -z "$grub_theme" ] || [ ! -f "$grub_theme" ]; then
        problem "GRUB_THEME does not point at an existing theme ($grub_theme)"
    fi
    grep -qx 'Theme=yaran' /etc/plymouth/plymouthd.conf 2>/dev/null || \
        problem 'Plymouth default theme is not yaran'
    test -f /usr/share/plymouth/themes/yaran/yaran.script || \
        problem 'Plymouth yaran theme files are missing'
    test -f /usr/share/plymouth/themes/yaran/background.png || \
        problem 'Plymouth yaran background image is missing'
    [ "$fail" -eq 0 ] && ok 'GRUB theme and Plymouth splash installed'
fi

# --- 7. Desktop: Hiddify (when shipped) ------------------------------------
if is_desktop && dpkg -s hiddify >/dev/null 2>&1; then
    test -x /usr/bin/hiddify || problem 'hiddify is installed but /usr/bin/hiddify is missing'
    if ldd /usr/share/hiddify/hiddify 2>/dev/null | grep -q 'not found'; then
        problem 'hiddify has unresolved shared libraries:'
        ldd /usr/share/hiddify/hiddify | grep 'not found' >&2
    fi
    [ "$fail" -eq 0 ] && ok 'hiddify launcher and libraries resolve'
fi

if [ "$fail" -ne 0 ]; then
    echo 'verify-image: image failed consistency checks; aborting build' >&2
    exit 1
fi
echo 'verify-image: all checks passed'
