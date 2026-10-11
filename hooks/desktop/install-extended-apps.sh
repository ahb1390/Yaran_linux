#!/bin/bash
# Extended-only: install the official .deb applications that ship outside any
# APT repository. Same pinned-release + SHA-256 verification as the common hook.
set -euo pipefail

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

install_deb() {
    local label="$1" url="$2" sha="$3" file="$work/pkg.deb"
    echo "extended-apps: installing $label"
    curl -fsSL --retry 3 --retry-delay 2 -o "$file" "$url"
    echo "$sha  $file" | sha256sum -c --status - || {
        echo "extended-apps: SHA-256 mismatch for $label" >&2
        exit 1
    }
    apt-get install -y "$file"
}

# VSCodium — official VS Code-compatible build (amd64 .deb from GitHub releases).
install_deb "VSCodium 1.135.06055" \
    "https://github.com/VSCodium/vscodium/releases/download/1.135.06055/codium_1.135.06055_amd64.deb" \
    "5f5c00a9da9d232e4c84e9eee68bbdeb4d8737462022626ce3bdb6948f3d8649"

# Obsidian — official release; note this application is NOT open source.
install_deb "Obsidian 1.14.4" \
    "https://github.com/obsidianmd/obsidian-releases/releases/download/v1.14.4/obsidian_1.14.4_amd64.deb" \
    "85b10dcba6edfc1c0460a6d18260cf31c30447a444bd858a6440b9c9c8806d25"

echo "extended-apps: done"
