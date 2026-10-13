# Hardware diagnostics guide

**English** ([hardware-diagnostics.md](hardware-diagnostics.md)) | فارسی ([hardware-diagnostics.fa.md](hardware-diagnostics.fa.md))

Every command below is **read-only** and safe to run on a production
machine. Run them when filing a hardware bug and attach the output (strip
serial numbers and MAC addresses before sharing).

## One-shot collection

```bash
{
  echo "== kernel/session =="; uname -a; echo "session=$XDG_SESSION_TYPE"
  echo "== cpu ==";  lscpu | grep -E 'Model name|Vendor|CPU\(s\)'
  echo "== pci ==";  lspci -nnk
  echo "== usb ==";  lsusb
  echo "== drm ==";  for d in /sys/class/drm/card[0-9]; do echo "$d driver=$(basename "$(readlink -f "$d/device/driver" 2>/dev/null)")"; done
  echo "== sound =="; aplay -l; arecord -l
  echo "== ucm ==";  ls /usr/share/alsa/ucm2 2>/dev/null | head
  echo "== wpctl =="; wpctl status
  echo "== camera =="; v4l2-ctl --list-devices 2>/dev/null || ls -l /sys/class/video4linux/
  echo "== power =="; upower -d; powerprofilesctl get
  echo "== thermals =="; for z in /sys/class/thermal/thermal_zone*; do echo "$(cat "$z/type")=$(cat "$z/temp")"; done
  echo "== battery wear =="; for b in /sys/class/power_supply/BAT*; do echo "design=$(cat "$b/energy_full_design" 2>/dev/null) full=$(cat "$b/energy_full" 2>/dev/null) cycles=$(cat "$b/cycle_count" 2>/dev/null)"; done
  echo "== firmware =="; dmesg 2>/dev/null | grep -iE 'firmware.*failed|direct firmware load' | head
} > /tmp/yaran-hw-report.txt 2>&1
```

## Interpreting the common cases

| Symptom | Likely layer | First check |
|---|---|---|
| No sound at all | mixer path / profile | `wpctl status` (sink exists?), `amixer -c1` (Speaker muted?), `journalctl --user -b \| grep -i pipewire` |
| Mic silent | input path / mute | `arecord -l` lists the device? pavucontrol Input Devices unmuted? |
| Glitchy audio under load | realtime scheduling | `journalctl --user -b \| grep RTKit` — non-zero means rtkit is missing |
| Brightness keys dead | powerdevil | `systemctl --user status plasma-powerdevil` (older) or check powerdevil package |
| Camera not offered in browser | permissions / device | `ls -l /dev/video*`, browser site permissions |
| Screen share picker empty | portal chain | `systemctl --user status xdg-desktop-portal xdg-desktop-portal-kde` |
| Runs hot | thermal policy | `thermald` active? `cat /sys/class/thermal/thermal_zone*/temp` under load |
| Battery drains fast | profile / brightness / wear | `powerprofilesctl get`, brightness level, `upower -d` (energy_full vs design) |

## What software cannot fix

* Speaker hiss or a microphone that clips at the hardware level.
* Cameras with fixed-focus, low-resolution sensors.
* Battery wear (`energy_full` far below `energy_full_design`).
* Thermal limits of the chassis — throttling under sustained load is the
  firmware protecting the CPU, not a distribution defect.

Report these as hardware limitations with evidence; do not paper over them
with gain or fan-control hacks.
