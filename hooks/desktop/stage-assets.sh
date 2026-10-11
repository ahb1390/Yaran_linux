#!/bin/bash
set -e
mkdir -p "$ROOTFS/.temp_assets"
cp -r ./assets/yaran-plasma-theme "$ROOTFS/.temp_assets/"
cp -a ./assets/wallpapers "$ROOTFS/.temp_assets/yaran-plasma-theme/usr/share/"
cp -r ./assets/calamares "$ROOTFS/.temp_assets/calamares/"
cp -a ./assets/fastfetch "$ROOTFS/.temp_assets/"
install -Dm 0644 ./yaran.svg "$ROOTFS/.temp_assets/yaran-plasma-theme/usr/share/icons/hicolor/scalable/apps/yaran.svg"
