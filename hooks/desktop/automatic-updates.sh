#!/bin/bash
# Background APT activity policy for the desktop images.
#
# Problem this solves: Debian's unattended-upgrades stack (apt-daily.timer,
# apt-daily-upgrade.timer and unattended-upgrades.service) takes the APT/DPKG
# locks at random moments — most notably right after the first boot, because
# both timers are Persistent and fire immediately once the machine is online.
# A user opening a terminal right after install then hits
# "Could not get lock /var/lib/dpkg/lock-frontend ... another process uses it"
# for minutes while the background job downloads and installs upgrades.
#
# Default policy for Yaran desktop images:
#   * no automatic apt-get update and no automatic package installation;
#   * security updates stay available on demand through `yaran-update`
#     (one command, user-initiated, interactive and interruptible);
#   * the unattended-upgrades tooling remains installed so users and the
#     documentation can re-enable automatic security updates if they want them
#     (see docs/updates-policy.md).
set -euo pipefail

echo 'Configuring on-demand package updates (no background APT locks)'

# 1) Turn the periodic APT jobs off. This file is the Debian-sanctioned place
#    for these keys; unattended-upgrades itself only reads them, so disabling
#    them here is sufficient and reversible.
cat > /etc/apt/apt.conf.d/20auto-upgrades << 'EOF'
// Yaran Linux default: updates are user-initiated (run `yaran-update`).
// To re-enable automatic daily security upgrades, set both values to "1"
// and re-enable apt-daily-upgrade.timer. See docs/updates-policy.md.
APT::Periodic::Update-Package-Lists "0";
APT::Periodic::Unattended-Upgrade "0";
APT::Periodic::Download-Upgradeable-Packages "0";
APT::Periodic::AutocleanInterval "7";
EOF

# 2) Make sure no timer or service can grab the APT/DPKG locks in the
#    background. `systemctl disable` works inside a build chroot (it only
#    edits symlinks), and the units stay installed and documented, so a user
#    can re-enable them at any time with `systemctl enable --now`.
for unit in apt-daily.timer apt-daily-upgrade.timer unattended-upgrades.service; do
    # capture instead of `| grep -q` (pipefail + short-circuiting grep is a
    # SIGPIPE trap; see hooks/common/verify-image.sh for the full note)
    unit_files=$(systemctl list-unit-files "$unit" --no-legend 2>/dev/null || true)
    case "$unit_files" in
        *"$unit"*)
            systemctl disable "$unit" 2>/dev/null || true
            echo "  disabled $unit"
            ;;
    esac
done

# 3) On-demand update helper shown in the menu and usable from a terminal.
#    Deliberately interactive: it never runs at boot and never holds a lock
#    the user did not ask for.
cat > /usr/local/bin/yaran-update << 'EOF'
#!/bin/sh
# Yaran Linux update helper — run from a terminal or the application menu.
set -eu
if [ "$(id -u)" -ne 0 ]; then
    exec sudo -- "$0" "$@"
fi
export DEBIAN_FRONTEND="${DEBIAN_FRONTEND:-interactive}"
echo 'Refreshing package lists ...'
apt-get update
echo
echo 'Installing available upgrades (interactive; Ctrl+C is safe) ...'
apt-get -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" \
    upgrade
echo
read -r -p 'Also remove now-unused packages? [y/N] ' answer || answer=n
case "$answer" in
    [Yy]*) apt-get autoremove --purge ;;
esac
echo 'Done.'
EOF
chmod 0755 /usr/local/bin/yaran-update

# 4) A desktop menu entry so the helper is discoverable without a terminal.
cat > /usr/share/applications/yaran-update.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=Yaran Updater
Name[fa]=به‌روزرسانی یاران
Comment=Check for and install system updates
Comment[fa]=بررسی و نصب به‌روزرسانی‌های سیستم
Exec=/usr/local/bin/yaran-update
Icon=system-software-update
Terminal=true
Categories=System;Settings;
EOF

echo 'Automatic updates: disabled by default; use yaran-update'
