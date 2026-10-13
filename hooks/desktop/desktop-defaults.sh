#!/bin/bash
set -e
echo 'Applying desktop, xdg and SDDM config'
cp -a /.temp_assets/yaran-plasma-theme/etc/xdg/. /etc/xdg/

# --- Font configuration -----------------------------------------------------
# Default families plus strong per-language preferences, so Persian and Arabic
# resolve to Vazirmatn / the Noto Arabic families instead of silently falling
# back to DejaVu Sans. CJK resolves to Noto Sans CJK (fontconfig ranks it
# highest for zh/ja/ko coverage), listed explicitly for deterministic results
# across Plasma, browsers, terminals and LibreOffice.
install -d -m 0755 /etc/fonts/conf.d
cat > /etc/fonts/conf.d/99-yaran-default-fonts.conf <<'EOF'
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <!-- Default families for the Yaran desktop. -->
  <alias>
    <family>sans-serif</family>
    <prefer>
      <family>Noto Sans</family>
      <family>Vazirmatn</family>
      <family>Noto Sans CJK SC</family>
    </prefer>
  </alias>
  <alias>
    <family>serif</family>
    <prefer>
      <family>Noto Serif</family>
      <family>Noto Naskh Arabic</family>
    </prefer>
  </alias>
  <alias>
    <family>monospace</family>
    <prefer><family>Noto Sans Mono</family></prefer>
  </alias>

  <!-- Persian: Vazirmatn first, Noto Arabic families as fallback. -->
  <match target="pattern">
    <test name="lang" compare="eq"><string>fa</string></test>
    <test name="family"><string>sans-serif</string></test>
    <edit name="family" mode="prepend" binding="strong">
      <string>Vazirmatn</string>
      <string>Noto Sans Arabic</string>
      <string>Noto Naskh Arabic</string>
    </edit>
  </match>

  <!-- Arabic: Noto Arabic families, Amiri as further fallback. -->
  <match target="pattern">
    <test name="lang" compare="eq"><string>ar</string></test>
    <test name="family"><string>sans-serif</string></test>
    <edit name="family" mode="prepend" binding="strong">
      <string>Noto Sans Arabic</string>
      <string>Noto Naskh Arabic</string>
      <string>Amiri</string>
    </edit>
  </match>

  <!-- Chinese (simplified + traditional), Japanese, Korean. -->
  <match target="pattern">
    <test name="lang" compare="eq"><string>zh-cn</string></test>
    <test name="family"><string>sans-serif</string></test>
    <edit name="family" mode="prepend" binding="strong"><string>Noto Sans CJK SC</string></edit>
  </match>
  <match target="pattern">
    <test name="lang" compare="eq"><string>zh-tw</string></test>
    <test name="family"><string>sans-serif</string></test>
    <edit name="family" mode="prepend" binding="strong"><string>Noto Sans CJK TC</string></edit>
  </match>
  <match target="pattern">
    <test name="lang" compare="eq"><string>ja</string></test>
    <test name="family"><string>sans-serif</string></test>
    <edit name="family" mode="prepend" binding="strong"><string>Noto Sans CJK JP</string></edit>
  </match>
  <match target="pattern">
    <test name="lang" compare="eq"><string>ko</string></test>
    <test name="family"><string>sans-serif</string></test>
    <edit name="family" mode="prepend" binding="strong"><string>Noto Sans CJK KR</string></edit>
  </match>
</fontconfig>
EOF
fc-cache -f

# --- SDDM -------------------------------------------------------------------
mkdir -p /etc/sddm.conf.d /etc/skel/Desktop
cp -a /.temp_assets/yaran-plasma-theme/etc/sddm.conf.d/. /etc/sddm.conf.d/
cp -a /.temp_assets/yaran-plasma-theme/etc/skel/Desktop/. /etc/skel/Desktop/
chmod 0755 /etc/skel/Desktop/*.desktop

# --- ~/Projects for every user ---------------------------------------------
# useradd copies /etc/skel into every new home directory, so users created by
# Calamares (or by hand) get ~/Projects with correct ownership automatically.
# The live user already exists at this point, so seed their home explicitly.
install -d -m 0755 /etc/skel/Projects
install -m 0644 /.temp_assets/skel-Projects-README.txt /etc/skel/Projects/README.txt
live_home=$(getent passwd admin | cut -d: -f6)
if [ -n "$live_home" ]; then
    install -d -m 0755 -o admin -g admin "$live_home/Desktop"
    cp -a /etc/skel/Desktop/. "$live_home/Desktop/"
    install -m 0755 -o admin -g admin /.temp_assets/yaran-plasma-theme/usr/share/applications/install-yaran.desktop "$live_home/Desktop/Install Yaran Linux.desktop"
    chown -R admin:admin "$live_home/Desktop"
    install -d -m 0755 -o admin -g admin "$live_home/Projects"
    install -m 0644 -o admin -g admin /.temp_assets/skel-Projects-README.txt "$live_home/Projects/README.txt"
fi
