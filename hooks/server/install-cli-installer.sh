#!/bin/bash
set -eu
install -D -o root -g root -m 0755 /.temp_assets/server/usr/local/bin/install-yaran /usr/local/bin/install-yaran
install -D -o root -g root -m 0440 /.temp_assets/server/etc/sudoers.d/90-yaran-installer /etc/sudoers.d/90-yaran-installer
install -D -o root -g root -m 0644 /.temp_assets/server/etc/systemd/system/yaran-installer.service /etc/systemd/system/yaran-installer.service
systemctl enable yaran-installer.service
