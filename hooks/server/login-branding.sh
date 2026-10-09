#!/bin/bash
set -eu
printf 'Yaran Linux Server 2.0 \\n \\l\n' > /etc/issue
printf 'Yaran Linux Server 2.0\n' > /etc/issue.net
mkdir -p /etc/default/grub.d
printf 'GRUB_DISTRIBUTOR="Yaran Linux Server 2.0"\n' > /etc/default/grub.d/50-yaran-server.cfg
cat > /etc/motd << 'EOF'
Welcome to Yaran Linux Server 2.0

Live account: admin
SSH is installed but disabled on live media. After changing the password, run:
  sudo passwd admin
  sudo systemctl enable --now ssh

Use nmcli for network configuration and nft for firewall management.

To install Yaran Linux, use a local console and run:
  install-yaran
EOF
