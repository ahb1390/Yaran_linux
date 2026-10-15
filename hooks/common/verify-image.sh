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
            \#*) continue ;;
            deb\ *|deb-src\ *)
                case "$line" in
                    *trusted=yes*|*allow-insecure=yes*|*check-valid-until=no*)
                        problem "insecure option in $file: $line"
                        ;;
                esac
                # Vendor repositories must pin their own signing key. Plain
                # Debian archives (the default mirror or any regional mirror
                # of it, e.g. a local university or ISP mirror) are verified
                # against debian-archive-keyring whatever host they use, so a
                # Debian suite without signed-by is fine — anything else is
                # not an acceptable source for a default image.
                case "$line" in
                    *signed-by=*)
                        key=$(printf '%s' "$line" | sed -n 's/.*signed-by=\([^] ]*\).*/\1/p')
                        if [ -n "$key" ] && [ ! -e "$key" ]; then
                            problem "signed-by keyring $key missing in $file"
                        fi
                        ;;
                    *trixie*|*stable*|*bookworm*|*bullseye*|*testing*|*sid*) : ;;
                    *) problem "unrecognized non-Debian source without signed-by in $file: $line" ;;
                esac
                ;;
        esac
    done < "$file"
done < <(find /etc/apt -maxdepth 2 -type f \( -name '*.list' -o -name 'sources.list' \) -print)

# deb822 (.sources) repositories carry the same fields as one stanza per
# source (URIs/Signed-By/Trusted). They get the identical policy: no
# insecure shortcuts, and any non-Debian origin must pin its own keyring.
while IFS= read -r file; do
    stanza=$(grep -Ev '^\s*(#|$)' "$file" || true)
    case "$stanza" in
        *'Trusted: yes'*|*'allow-insecure: yes'*|*'check-valid-until: no'*)
            problem "insecure option in deb822 source $file" ;;
    esac
    while IFS= read -r uri; do
        [ -n "$uri" ] || continue
        case "$uri" in
            *debian.org*) continue ;;
        esac
        case "$stanza" in
            *'Signed-By:'*)
                key=$(printf '%s\n' "$stanza" | sed -n 's/^Signed-By: *//p' | head -n1)
                if [ -n "$key" ] && [ ! -e "$key" ]; then
                    problem "Signed-By keyring $key missing in $file"
                fi
                ;;
            *) problem "non-Debian deb822 source without Signed-By in $file: $uri" ;;
        esac
    done < <(printf '%s\n' "$stanza" | sed -n 's/^URIs: *//p')
done < <(find /etc/apt -maxdepth 2 -type f -name '*.sources' -print 2>/dev/null)

[ "$fail" -eq 0 ] && ok 'APT sources are signed and minimal'

# If trixie-backports is enabled there must be a pin proving it is required.
if grep -Rqs 'trixie-backports' /etc/apt/ 2>/dev/null; then
    if ! grep -Rqs 'Pin: release n=trixie-backports' /etc/apt/preferences.d/ 2>/dev/null; then
        problem 'trixie-backports enabled without a package pin justifying it'
    else
        ok 'trixie-backports present with an explicit package pin'
    fi
fi

# Vendor (non-Debian) repositories may only exist when the manifest opted in
# with "vendor_repositories": true. hooks/desktop/vendor-repos*.sh record
# that consent by listing the vendor ORIGIN HOST they enabled in
# /etc/apt/yaran-vendor-repos. Matching is by host, not by filename, because
# a shipped third-party package can write its own source file for the same
# origin: google-chrome-stable's postinst unconditionally creates
# /etc/apt/sources.list.d/google-chrome.sources (deb822) on a new install,
# next to the .list file the hook wrote. The manifest opted in to that
# ORIGIN, so both files are covered — while any origin without a consent
# entry still fails the build.
consent=$(tr '\n' ' ' < /etc/apt/yaran-vendor-repos 2>/dev/null || true)
base_hosts=$(sed -n 's|^deb \(\[[^]]*\] \)\?https\?://\([^/ ]*\).*|\2|p' /etc/apt/sources.list 2>/dev/null || true)
# Extract the origin host from either one-line (.list) or deb822 (.sources)
# syntax, so a vendor source cannot dodge the consent check by switching
# format.
source_hosts() {
    case "$1" in
        *.sources)
            sed -n 's/^URIs: *//p' "$1" | sed -n 's|^\(\[[^]]*\] \)\?https\?://\([^/ ]*\).*|\2|p'
            ;;
        *)
            sed -n 's|^deb \(\[[^]]*\] \)\?https\?://\([^/ ]*\).*|\2|p' "$1"
            ;;
    esac
}
while IFS= read -r file; do
    while IFS= read -r host; do
        [ -n "$host" ] || continue
        case "$host" in
            *.debian.org) continue ;;
        esac
        case "$base_hosts" in
            *"$host"*) continue ;;
        esac
        case " $consent " in
            *" $host "*) : ;;
            *) problem "vendor repository host $host in $file has no vendor_repositories opt-in" ;;
        esac
    done < <(source_hosts "$file")
done < <(find /etc/apt/sources.list.d -maxdepth 1 -type f \( -name '*.list' -o -name '*.sources' \) -print 2>/dev/null)
[ "$fail" -eq 0 ] && ok 'no vendor APT repository without explicit opt-in'

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

# --- 3b. Desktop: audio quality, realtime scheduling and memory -----------
# rtkit grants PipeWire/WirePlumber realtime priority; without it every
# session logs "RTKit error: ServiceUnknown" and audio runs with worse
# glitch resistance. alsa-ucm-conf provides the codec UCM profiles that
# WirePlumber uses for correct speaker/headphone/mic path handling.
# zram-tools adds compressed RAM swap — Calamares installs without a swap
# partition by default, leaving the installed system with none at all.
if is_desktop; then
    for pkg in rtkit alsa-ucm-conf libspa-0.2-bluetooth zram-tools; do
        dpkg -s "$pkg" >/dev/null 2>&1 || problem "missing audio/memory package: $pkg"
    done
    test -d /usr/share/alsa/ucm2 || problem 'ALSA UCM2 profile tree is missing'
    if [ "$(dpkg --print-architecture)" = amd64 ]; then
        dpkg -s thermald >/dev/null 2>&1 || \
            problem 'thermald missing on amd64 (Intel laptop thermal management)'
    fi
    [ "$fail" -eq 0 ] && ok 'rtkit/UCM/zram/thermald present'
fi

# --- 4. Desktop: font coverage ---------------------------------------------
if is_desktop; then
    for pkg in fonts-vazirmatn fonts-vazirmatn-variable fonts-noto-core \
               fonts-noto-cjk fonts-noto-mono fonts-noto-ui-core \
               fonts-noto-color-emoji; do
        dpkg -s "$pkg" >/dev/null 2>&1 || problem "missing font package: $pkg"
    done
    test -f /etc/fonts/conf.d/99-yaran-default-fonts.conf || \
        problem 'Yaran fontconfig defaults missing'
    # Actual script coverage in fontconfig — a package being installed is not
    # proof that text renders. Each line must resolve to at least one family.
    #
    # NOTE: output is captured into a variable instead of piping into
    # `grep -q`. With `set -o pipefail`, grep -q exits on the first match
    # while fc-list is still writing; on images with thousands of fonts
    # (Extended with fonts-noto-extra / cjk-extra) fc-list then dies with
    # SIGPIPE and the pipeline fails even though the font IS present.
    while IFS='|' read -r lang family; do
        [ -n "$lang" ] || continue
        lang_fonts=$(fc-list ":lang=$lang" family 2>/dev/null || true)
        if [ -z "$lang_fonts" ]; then
            problem "no font registered for language '$lang' ($family)"
        fi
    done <<'EOF'
fa|Persian (Vazirmatn)
ar|Arabic (Noto)
he|Hebrew (Noto)
hi|Devanagari (Noto)
bn|Bengali (Noto)
ta|Tamil (Noto)
th|Thai (Noto)
lo|Lao (Noto)
km|Khmer (Noto)
my|Myanmar (Noto)
bo|Tibetan (Noto Serif)
hy|Armenian (Noto)
ka|Georgian (Noto)
am|Ethiopic (Noto)
el|Greek (Noto)
ru|Cyrillic (Noto)
zh-cn|Chinese simplified (Noto CJK)
zh-tw|Chinese traditional (Noto CJK)
ja|Japanese (Noto CJK)
ko|Korean (Noto CJK)
EOF
    zh_fonts=$(fc-list :lang=zh family 2>/dev/null || true)
    case "$zh_fonts" in
        *'Noto Sans CJK'*) : ;;
        *) problem 'no CJK font registered in fontconfig' ;;
    esac
    fa_fonts=$(fc-list :lang=fa family 2>/dev/null || true)
    case "$fa_fonts" in
        *Vazirmatn*) : ;;
        *) problem 'no Persian font registered in fontconfig' ;;
    esac
    [ "$fail" -eq 0 ] && ok 'font script coverage verified (20 languages)'
fi

# --- 5. Desktop: skel and wallet policy ------------------------------------
if is_desktop; then
    test -d /etc/skel/Projects || problem '/etc/skel/Projects is missing'
    # (checks capture file contents into variables instead of piping into
    # grep -q — see the font section for the pipefail/SIGPIPE rationale)
    wallet_cfg=$(sed -n '/^\[Wallet\]/,+2p' /etc/xdg/kdeglobals 2>/dev/null || true)
    case "$wallet_cfg" in
        *Enabled=false*) : ;;
        *) problem 'KWallet is not disabled in /etc/xdg/kdeglobals' ;;
    esac
    [ "$fail" -eq 0 ] && ok 'skel Projects folder present; KWallet disabled'
fi

# --- 5b. Desktop: KDE shell, power stack and no GNOME apps -----------------
# powerdevil is the KDE component behind brightness keys, the battery applet,
# lid-close and suspend policies; without it Fn brightness keys are dead.
# TLP must never share the machine with power-profiles-daemon.
if is_desktop; then
    for pkg in dolphin plasma-pa bluedevil plasma-nm powerdevil upower \
               kinfocenter fwupd; do
        dpkg -s "$pkg" >/dev/null 2>&1 || problem "missing KDE component: $pkg"
    done
    for pkg in nautilus gnome-terminal file-roller evince eog totem rhythmbox tlp zenity; do
        if dpkg -s "$pkg" >/dev/null 2>&1; then
            problem "unwanted package installed: $pkg"
        fi
    done
    mime_cfg=$(sed -n '/\[Default Applications\]/,+3p' /etc/xdg/mimeapps.list 2>/dev/null || true)
    case "$mime_cfg" in
        *'inode/directory=org.kde.dolphin.desktop'*) : ;;
        *) problem 'Dolphin is not the default file manager in /etc/xdg/mimeapps.list' ;;
    esac
    for app in dolphin kate konsole gwenview okular ark; do
        entry=$(find /usr/share/applications -maxdepth 1 -iname "*${app}*" \
                -print -quit 2>/dev/null || true)
        [ -n "$entry" ] || problem "menu entry missing for $app"
    done
    [ "$fail" -eq 0 ] && ok 'KDE shell/power stack present, GNOME apps absent, Dolphin default'
fi

# --- 5c. Desktop: firmware coverage ----------------------------------------
if is_desktop; then
    for pkg in firmware-misc-nonfree bluez-firmware; do
        dpkg -s "$pkg" >/dev/null 2>&1 || problem "missing firmware package: $pkg"
    done
    [ "$fail" -eq 0 ] && ok 'base firmware packages installed'
fi

# --- 6. Desktop: boot branding ---------------------------------------------
if is_desktop; then
    grub_cfg_file=/etc/default/grub.d/50-yaran.cfg
    grub_theme=$(sed -n 's/^GRUB_THEME="\(.*\)"/\1/p' "$grub_cfg_file" 2>/dev/null || true)
    if [ -z "$grub_theme" ] || [ ! -f "$grub_theme" ]; then
        problem "GRUB_THEME does not point at an existing theme ($grub_theme)"
    fi
    # update-grub's 05_debian_theme emits `background_image <path>` for
    # GRUB_BACKGROUND WITHOUT quoting it, so a path containing whitespace
    # is truncated at the first space by GRUB and every boot of the
    # installed system fails with "bitmap file ... is of unsupported format".
    grub_bg=$(sed -n 's/^GRUB_BACKGROUND="\(.*\)"/\1/p' "$grub_cfg_file" 2>/dev/null || true)
    if [ -n "$grub_bg" ]; then
        case "$grub_bg" in
            *[[:space:]]*)
                problem "GRUB_BACKGROUND contains whitespace; update-grub emits it unquoted ($grub_bg)"
                ;;
            *.png|*.jpg|*.jpeg|*.tga) : ;;
            *) problem "GRUB_BACKGROUND has an unsupported image format ($grub_bg)" ;;
        esac
        [ -f "$grub_bg" ] || problem "GRUB_BACKGROUND does not point at an existing file ($grub_bg)"
    fi
    # GRUB 2.12 (Debian trixie) has no terminal-color theme property and
    # raises "unknown property" on every boot when the theme uses it.
    # GRUB only parses a property when it appears at the start of a line;
    # '#' comment lines (which legitimately DOCUMENT this history in
    # theme.txt) are ignored by the parser, so they must be filtered here
    # too — otherwise the check reports a false positive on the very
    # comment that explains why terminal-color was removed.
    theme_content=$(grep -Ev '^[[:space:]]*#' \
        /usr/share/grub/themes/yaran/theme.txt 2>/dev/null || true)
    case "$theme_content" in
        *'terminal-color'*)
            problem 'the installed GRUB theme uses terminal-color, unknown to GRUB 2.12'
            ;;
    esac
    grep -qx 'Theme=yaran' /etc/plymouth/plymouthd.conf 2>/dev/null || \
        problem 'Plymouth default theme is not yaran'
    test -f /usr/share/plymouth/themes/yaran/yaran.script || \
        problem 'Plymouth yaran theme files are missing'
    test -f /usr/share/plymouth/themes/yaran/background.png || \
        problem 'Plymouth yaran background image is missing'
    [ "$fail" -eq 0 ] && ok 'GRUB theme and Plymouth splash installed'
fi

# --- 7. Desktop: Node.js toolchain (only images that ship it) ---------------
# The Extended image pins the official Node.js 26 release toolchain under
# /usr/local (hooks/desktop/install-nodejs26.sh) instead of Debian's
# nodejs 20.x package; Debian trixie cannot provide 26.x without an external
# APT repository, which the repository policy forbids.
if command -v node >/dev/null 2>&1; then
    node_version=$(node --version 2>/dev/null || true)
    case "$node_version" in
        v26.*) ok "Node.js toolchain present ($node_version)" ;;
        *) problem "node is installed but is not the pinned Node.js 26 toolchain ($node_version)" ;;
    esac
    npm_version=$(npm --version 2>/dev/null || true)
    if [ -z "$npm_version" ]; then
        problem 'npm is missing or broken next to the Node.js toolchain'
    fi
fi

# --- 8. Desktop: Hiddify (when shipped) ------------------------------------
if is_desktop && dpkg -s hiddify >/dev/null 2>&1; then
    test -x /usr/bin/hiddify || problem 'hiddify is installed but /usr/bin/hiddify is missing'
    hiddify_libs=$(ldd /usr/share/hiddify/hiddify 2>/dev/null || true)
    case "$hiddify_libs" in
        *'not found'*)
            problem 'hiddify has unresolved shared libraries:'
            printf '%s\n' "$hiddify_libs" | grep 'not found' >&2 || true
            ;;
    esac
    [ "$fail" -eq 0 ] && ok 'hiddify launcher and libraries resolve'
fi

if [ "$fail" -ne 0 ]; then
    echo 'verify-image: image failed consistency checks; aborting build' >&2
    exit 1
fi
echo 'verify-image: all checks passed'
