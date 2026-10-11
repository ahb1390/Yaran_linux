#!/bin/bash
set -e
echo 'Installing Plasma Theme and Wallpapers'
cp -a /.temp_assets/yaran-plasma-theme/usr/share/plasma/. /usr/share/plasma/
mkdir -p /usr/share/wallpapers
cp -a /.temp_assets/yaran-plasma-theme/usr/share/wallpapers/. /usr/share/wallpapers/
mkdir -p /usr/share/sddm/themes
cp -a /.temp_assets/yaran-plasma-theme/usr/share/sddm/themes/. /usr/share/sddm/themes/
mkdir -p /usr/share/color-schemes
cp -a /.temp_assets/yaran-plasma-theme/usr/share/color-schemes/. /usr/share/color-schemes/
