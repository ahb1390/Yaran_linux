#!/bin/bash
# Install a pinned, checksum-verified copy of ble.sh (menu completion,
# autosuggestions, syntax highlighting) into /usr/share/ble.sh.
#
# Reproducibility and safety rules:
#   * exact release tarball from the official GitHub release page;
#   * SHA-256 recorded from that same artifact — a mismatch aborts the build;
#   * no `curl | bash`: the archive is extracted and *then* sourced from the
#     installed copy by /usr/share/yaran/bash/yaran-bashrc;
#   * license: BSD-3-Clause (stated in the file header of the release
#     artifact), compatible with the rest of the image.
#
# Desktop editions only; the server edition keeps plain bash-completion.
set -euo pipefail

BLE_VERSION="0.4.0-devel3"
BLE_TARBALL="ble-${BLE_VERSION}-2.tar.xz"
BLE_SHA256="bdcdcfff216495403adf82a701fe41675f64b64644dc77caabd3e015871ebd61"
BLE_URL="https://github.com/akinomyoga/ble.sh/releases/download/v${BLE_VERSION}/${BLE_TARBALL}"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

echo "install-ble: downloading ble.sh ${BLE_VERSION}"
if ! curl -fsSL --retry 3 --retry-delay 2 -o "$work/ble.tar.xz" "$BLE_URL"; then
    echo "install-ble: download failed from $BLE_URL" >&2
    exit 1
fi
if ! echo "$BLE_SHA256  $work/ble.tar.xz" | sha256sum -c --status -; then
    echo "install-ble: SHA-256 mismatch for ble.sh ${BLE_VERSION}" >&2
    echo "  expected: $BLE_SHA256" >&2
    echo "  actual  : $(sha256sum "$work/ble.tar.xz" | cut -d' ' -f1)" >&2
    exit 1
fi

mkdir -p "$work/extract"
tar -xJf "$work/ble.tar.xz" -C "$work/extract"
entry="$work/extract/ble-${BLE_VERSION}/ble.sh"
if [ ! -f "$entry" ]; then
    echo "install-ble: archive layout unexpected; ble.sh entry not found" >&2
    exit 1
fi
if ! bash -n "$entry"; then
    echo "install-ble: ble.sh fails a syntax check with the system bash" >&2
    exit 1
fi

rm -rf /usr/share/ble.sh
mkdir -p /usr/share/ble.sh
cp -a "$work/extract/ble-${BLE_VERSION}/." /usr/share/ble.sh/

# Record the provenance so the installed system can answer "what is this?".
cat > /usr/share/ble.sh/yaran-provenance << EOF
source: $BLE_URL
version: $BLE_VERSION
sha256: $BLE_SHA256
license: BSD-3-Clause
EOF

echo "install-ble: ble.sh ${BLE_VERSION} installed"
