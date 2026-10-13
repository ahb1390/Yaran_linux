#!/bin/bash
# Install the Yaran Bash experience configuration system-wide.
#
# The configuration lives in /usr/share/yaran/bash/yaran-bashrc and is
# sourced from /etc/bash.bashrc — Debian's bash reads that file for every
# interactive shell, so the live session, users created by Calamares and
# existing users all get the experience without their personal ~/.bashrc
# being rewritten (user files still load afterwards and may override).
#
# Idempotent: re-running the hook never duplicates the source line.
set -euo pipefail

echo 'Installing Yaran Bash configuration'

install -d -m 0755 /usr/share/yaran/bash
install -m 0644 /.temp_assets/bash/yaran-bashrc /usr/share/yaran/bash/yaran-bashrc

# Syntax-check with the exact bash that will source it.
if ! bash -n /usr/share/yaran/bash/yaran-bashrc; then
    echo 'bash-experience: yaran-bashrc fails the syntax check' >&2
    exit 1
fi

marker='/usr/share/yaran/bash/yaran-bashrc'
if ! grep -qs "$marker" /etc/bash.bashrc; then
    cat >> /etc/bash.bashrc << 'EOF'

# Yaran Linux bash experience (interactive shells only; see
# /usr/share/yaran/bash/yaran-bashrc — colors, history, git prompt, and
# ble.sh menu completion when installed).
if [ -r /usr/share/yaran/bash/yaran-bashrc ]; then
    . /usr/share/yaran/bash/yaran-bashrc
fi
EOF
fi

echo 'bash-experience: installed'
