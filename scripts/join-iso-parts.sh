#!/usr/bin/env bash
# Reassemble a release ISO downloaded as numbered parts.
set -euo pipefail

iso=${1:?Usage: scripts/join-iso-parts.sh FILE.iso}
case "$iso" in
  *.iso) ;;
  *) echo "The output filename must end in .iso" >&2; exit 2 ;;
esac

parts_manifest="${iso}.parts.sha256"
if [[ ! -f "$parts_manifest" ]]; then
  echo "Missing parts checksum manifest: $parts_manifest" >&2
  exit 1
fi
if [[ -e "$iso" ]]; then
  echo "Refusing to overwrite existing file: $iso" >&2
  exit 1
fi

shopt -s nullglob
parts=( "${iso}.part"* )
if (( ${#parts[@]} == 0 )); then
  echo "No parts found for $iso" >&2
  exit 1
fi

echo "Verifying downloaded parts..."
sha256sum --check -- "$parts_manifest"

echo "Reassembling $iso..."
cat -- "${parts[@]}" > "$iso"

if [[ -f "${iso}.sha256" ]]; then
  echo "Verifying reconstructed ISO..."
  sha256sum --check -- "${iso}.sha256"
fi

echo "Done: $iso"
