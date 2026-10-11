#!/bin/bash
set -eu

install -D -o root -g root -m 0644 \
    /.temp_assets/fastfetch/config.jsonc /etc/fastfetch/config.jsonc
install -D -o root -g root -m 0644 \
    /.temp_assets/fastfetch/yaran.txt /usr/share/fastfetch/yaran.txt

if ! grep -Fq '# Yaran Linux Fastfetch' /etc/bash.bashrc; then
    cat >> /etc/bash.bashrc <<'EOF'

# Yaran Linux Fastfetch
if [[ $- == *i* && -t 1 && -z ${YARAN_FASTFETCH_SHOWN:-} ]] &&
   command -v fastfetch >/dev/null 2>&1; then
    export YARAN_FASTFETCH_SHOWN=1
    fastfetch --config /etc/fastfetch/config.jsonc || true
fi
EOF
fi
