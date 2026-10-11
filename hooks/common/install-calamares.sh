#!/bin/bash
set -eu
echo 'Installing Calamares config and branding'
cp -a /.temp_assets/calamares/. /etc/calamares/
install -Dm0755 /.temp_assets/calamares/helpers/yaran-grub-install /usr/local/sbin/yaran-grub-install
if [ -d /.temp_assets/server ]; then
    cp -a /.temp_assets/server/. /
    chown root:root /usr/local/bin/install-yaran /etc/sudoers.d/90-yaran-installer
    chmod 0755 /usr/local/bin/install-yaran
    chmod 0440 /etc/sudoers.d/90-yaran-installer
fi
