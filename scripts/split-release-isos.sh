#!/usr/bin/env bash
# Split every built ISO into GitHub-release-safe chunks.
set -euo pipefail
shopt -s nullglob

cd "$(dirname "$0")/../output"
isos=( *.iso )
if (( ${#isos[@]} == 0 )); then
  echo "No ISO files found in output/" >&2
  exit 1
fi

for iso in "${isos[@]}"; do
  echo "Splitting $iso into chunks no larger than 1800 MiB"
  split --bytes=1800M --numeric-suffixes=1 --suffix-length=3 -- "$iso" "${iso}.part"

  parts=( "${iso}.part"* )
  if (( ${#parts[@]} == 0 )); then
    echo "No split parts were created for $iso" >&2
    exit 1
  fi

  sha256sum -- "${parts[@]}" > "${iso}.parts.sha256"
  rm -- "$iso"
done
