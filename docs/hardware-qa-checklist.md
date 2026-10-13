# Real-hardware QA checklist

**English** ([hardware-qa-checklist.md](hardware-qa-checklist.md)) | فارسی ([hardware-qa-checklist.fa.md](hardware-qa-checklist.fa.md))

Everything in this list needs the actual ISO on actual hardware (or a VM with
a desktop session); it cannot be covered by CI. Run it once per release
candidate and record the result per item.

## 1. Install (Calamares)

- [ ] Boot the ISO (UEFI machine, then if available a legacy-BIOS machine).
- [ ] Complete the install; the **Finished** page appears.
- [ ] The finished page offers «Restart now after installation» — it is
      ticked by default; untick it, click Done, confirm the system does **not**
      restart; reboot manually and confirm it boots.
- [ ] Install again; leave the box ticked, click Done: the machine reboots
      once and lands in the SDDM of the installed system (no live autologin).
- [ ] Deliberately fail an install (e.g. cancel partitioning) and confirm no
      restart is offered.

## 2. APT / updates

- [ ] Immediately after the first login (within the first 5 minutes), open a
      terminal and run `apt update && apt install -y sl`; it must complete
      without any lock message.
- [ ] `systemctl list-timers 'apt*'` shows no `apt-daily*` timers.
- [ ] `yaran-update` (menu: «Yaran Updater») completes an update cycle.
- [ ] `/etc/apt/sources.list` + `/etc/apt/sources.list.d/` contain only the
      expected repositories and `apt update` ends without GPG/404 errors.

## 3. Hiddify

- [ ] Launch **Hiddify** from the KDE menu; the window opens as a normal
      user (no root, no terminal).
- [ ] Launch it from a terminal: `hiddify` starts without
      `error while loading shared libraries`.
- [ ] A profile can be imported and the app connects (network-dependent —
      record separately from the two items above).

## 4. Screen sharing (Chrome and Google Meet)

Test on **both** session types offered by SDDM (Wayland and X11):

- [ ] In Chrome: share → «Your entire screen» → the picker shows a live
      preview of each monitor and sharing works.
- [ ] In Chrome: share → «Window» → selecting a window shares that window.
- [ ] In Google Meet (meet.google.com): share → «Entire screen» → the
      browser permission prompt appears and the participant view shows the
      screen (join from a phone/second account if possible).
- [ ] `systemctl --user status xdg-desktop-portal xdg-desktop-portal-kde`
      are active after opening the picker once.
- [ ] No browser flags were needed (`chrome://flags` untouched).

## 5. Fonts

- [ ] Persian text in Plasma (labels, Dolphin), Chrome, Konsole, LibreOffice
      renders with Vazirmatn (Settings → Fonts → sans-serif shows the Yaran
      defaults).
- [ ] A Simplified Chinese, Traditional Chinese, Japanese and Korean page
      renders without tofu boxes in Chrome.
- [ ] Emoji reactions render in color in Chrome.
- [ ] In the installer (Calamares), Persian locale text (if selected) renders
      correctly.

## 6. GRUB (installed system)

- [ ] After install, reboot: GRUB menu shows the Yaran background, title and
      styled menu — not the plain black Debian menu.
- [ ] «Advanced options» still offers recovery entries; the machine's other
      OSes (if any) are still listed (os-prober).
- [ ] On a machine/VM without working graphics, the menu falls back to the
      text console and the system still boots (`nomodeset` entry works).

## 7. Boot splash (Plymouth)

- [ ] The installed system shows the Yaran splash (logo image) between GRUB
      and the SDDM greeter, with no wall of kernel text in normal boots.
- [ ] `plymouth-set-default-theme -l` lists `yaran` and
      `/etc/plymouth/plymouthd.conf` says `Theme=yaran`.
- [ ] Booting the `nomodeset`/recovery entry falls back to text without
      hanging.

## 8. KDE Wallet

- [ ] First login of a **newly created** user (Settings → Users → add user):
      no wallet creation dialog and no password prompt appears.
- [ ] Kate/Dolphin password storage actions fail gracefully (no crash).

## 9. ~/Projects

- [ ] A user created during install has `~/Projects` with their own
      ownership after first login.
- [ ] A user created afterwards (Settings → Users) also has `~/Projects`.

## 10. General smoke

- [ ] Wi-Fi connects, audio plays, Bluetooth pairs (if hardware present).
- [ ] Shutdown and reboot are clean (Plymouth hands over to SDDM and back
      without a text-mode flash).

## 11. Laptop keys (volume, brightness, media)

Test on a laptop; run `wev` (or `sudo showkey --keycodes` on a TTY) once to
see which keycodes the kernel actually emits, so a failure can be attributed
to a layer instead of guessed at.

- [ ] Volume up / down changes the **real** output level (play a YouTube
      video and watch both the OSD and the audible level); volume mute
      toggles audibly.
- [ ] After connecting headphones or a USB/Bluetooth speaker, the keys still
      control the newly selected sink; switching the output device in the
      audio applet restores control.
- [ ] After suspend/resume, volume keys still work.
- [ ] Brightness up/down changes the actual panel brightness (not just an
      OSD): watch `/sys/class/backlight/*/brightness` or use the slider in
      the battery applet.
- [ ] Keyboard backlight keys (if the laptop has them) toggle the
      backlight.
- [ ] Play/pause/next/previous control a running player (VLC, Chrome tab
      with media).
- [ ] If a key does nothing: with `wev` open, press it. No event → the
      problem is firmware/ACPI on that laptop model (note the exact model
      and key); event present but no action → check
      System Settings → Shortcuts → Global Shortcuts for conflicting
      bindings. Report which layer failed.

## 12. Power management (laptops)

- [ ] The battery applet in the system tray shows percentage and AC/battery
      state correctly.
- [ ] System Settings → Power Management opens (powerdevil) and offers
      screen-off and suspend timeouts; changes take effect.
- [ ] Closing the laptop lid suspends the machine; opening it resumes.
- [ ] After resume: display, sound, Wi-Fi and the volume keys all work.
- [ ] The power profile switch (Balanced / Power Saver, from the battery
      applet) changes profiles without errors — `powerprofilesctl get`
      confirms.
- [ ] `systemctl status tlp` shows the unit does not exist (TLP is excluded
      to avoid conflicting with power-profiles-daemon).
- [ ] On a desktop (no battery): the power applet degrades gracefully and
      nothing crashes.

## 13. KDE-only experience and default applications

- [ ] The menu shows Dolphin, Kate, Konsole, Gwenview, Okular, Ark, System
      Settings, Info Center — and **no** GNOME application (no "Files",
      "Terminal", "Archive Manager", "Document Viewer").
- [ ] `dpkg -l nautilus gnome-terminal file-roller evince` reports none
      installed.
- [ ] Double-clicking a folder in Dolphin, clicking the Home icon on the
      desktop and opening a folder from Chrome all use Dolphin; `xdg-mime
      query default inode/directory` prints `org.kde.dolphin.desktop`.
- [ ] Images open in Gwenview, PDFs in Okular, archives in Ark.
- [ ] A user created after install sees the same defaults.

## 14. World-wide font coverage

Paste these samples into Konsole, Dolphin's rename field and LibreOffice;
each must render without tofu boxes (□) or fallback boxes:

- Persian: یاران لینوکس — العربية हिन्दी ไทย
- Scripts: ગુજરાતી (Gujarati), ಕನ್ನಡ (Kannada), မြန်မာ (Myanmar),
  ქართული (Georgian), Հայերեն (Armenian), አማርኛ (Ethiopic),
  བོད་ཡིག (Tibetan), ភាសាខ្មែរ (Khmer), ລາວ (Lao), עברית (Hebrew)
- CJK: 简体中文, 繁體中文, 日本語, 한국어
- Emoji: 🚀 👍 🇮🇷 (color, not monochrome)

- [ ] All four groups render correctly in Chrome, Firefox, Konsole,
      Dolphin and LibreOffice.
- [ ] `fc-list :lang=xx` returns a family for each of the languages above.

## 15. Firmware and hardware tooling

- [ ] Info Center opens and shows CPU, memory, graphics (Mesa/DRI) and disk
      information.
- [ ] Discover → Firmware section (fwupd backend) lists the device or
      cleanly reports "no updatable devices" — never a crash.
- [ ] Touchpad: two-finger scrolling and tap-to-click work (libinput).
- [ ] Wi-Fi, Bluetooth, webcam and card reader are detected on at least one
      Intel and one AMD/Realtek/Broadcom machine if available.

## 16. Audio quality (speakers, headphone, microphone, HDMI, Bluetooth)

- [ ] Stereo test (e.g. a "left/right stereo test" video): both channels
      are audible on the speakers; no crackle or distortion at 80% volume.
- [ ] Plugging in headphones switches the output automatically and without
      a loud pop; unplugging returns to the speakers.
- [ ] Microphone: record and play back —
      `arecord -f cd -d 5 /tmp/mic-test.wav && aplay /tmp/mic-test.wav` —
      the voice is clearly recognizable, not clipped or inaudible.
- [ ] In Google Meet's microphone test the internal mic is picked up and
      the level meter reacts.
- [ ] If the mic is noisy at defaults, lower "Internal Mic Boost" once in
      pavucontrol (Input Devices) — this is a per-device runtime setting,
      not something the image should hardcode.
- [ ] HDMI: with a TV connected, HDMI audio appears as an output and plays.
- [ ] Bluetooth: pair headphones, confirm A2DP in `wpctl status`, play
      music; note that microphone over Bluetooth (HFP) is inherently low
      quality on most headsets — a hardware/codec limit, not a distro bug.
- [ ] After suspend/resume the default output is still correct and audio
      plays.
- [ ] `journalctl --user -b | grep -c RTKit` prints 0 (rtkit is present and
      PipeWire gets realtime scheduling).

## 17. Camera (video calls)

- [ ] `v4l2-ctl --list-devices` (Extended image) lists the camera; the
      kernel log has no `uvcvideo` errors.
- [ ] In meet.google.com → camera test: preview appears, and the offered
      resolutions match the sensor (e.g. 640×480 on old VGA modules — a
      sensor limit, not software).
- [ ] The browser asks for camera permission once and remembers it.
- [ ] Video is usable in normal room light; in dark rooms judge the sensor
      honestly — noisier image = physical sensor limit, do not "fix" it
      with gain filters.
- [ ] Switching cameras (if several exist) in the Meet selector works.
