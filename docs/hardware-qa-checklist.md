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
