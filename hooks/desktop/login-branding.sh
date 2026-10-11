#!/bin/bash
set -eu
printf 'Yaran Linux 2.0 \\n \\l\n' > /etc/issue
printf 'Yaran Linux 2.0\n' > /etc/issue.net
mkdir -p /etc/default/grub.d
cat > /etc/default/grub.d/50-yaran.cfg <<'EOF'
GRUB_DISTRIBUTOR="Yaran Linux 2.0"
GRUB_BACKGROUND="/usr/share/wallpapers/Yaran Emblem/contents/images/1585x992.png"
EOF
