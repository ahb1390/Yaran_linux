# راهنمای تشخیص سخت‌افزار

**English** ([hardware-diagnostics.md](hardware-diagnostics.md)) | فارسی ([hardware-diagnostics.fa.md](hardware-diagnostics.fa.md))

همه‌ی فرمان‌های زیر **فقط‌خواندنی** هستند و روی سیستم در حال استفاده امن‌اند. هنگام گزارش باگ سخت‌افزاری آن‌ها را اجرا و خروجی را پیوست کنید (قبل از اشتراک‌گذاری، شماره‌سریال‌ها و MAC را حذف کنید).

## جمع‌آوری یک‌جا

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

## تفسیر موارد رایج

| علامت | لایه‌ی محتمل | اولین بررسی |
|---|---|---|
| هیچ صدایی نیست | مسیر میکسر / پروفایل | `wpctl status` (Sink هست؟) ، `amixer -c1` (Speaker قفل است؟) ، `journalctl --user -b \| grep -i pipewire` |
| میکروفون بی‌صدا است | مسیر ورودی / Mute | `arecord -l` دستگاه را می‌بیند؟ در pavucontrol ورودی Mute نیست؟ |
| صدا هنگام بار پاره می‌شود | زمان‌بندی realtime | `journalctl --user -b \| grep RTKit` — صفر نبودن یعنی rtkit نیست |
| کلیدهای روشنایی کار نمی‌کنند | powerdevil | وجود بسته‌ی powerdevil و `systemctl status power-profiles-daemon` |
| دوربین در مرورگر نیست | مجوز / دستگاه | `ls -l /dev/video*` و مجوزهای سایت مرورگر |
| انتخاب‌گر اشتراک صفحه خالی است | زنجیره‌ی Portal | `systemctl --user status xdg-desktop-portal xdg-desktop-portal-kde` |
| سیستم داغ می‌کند | سیاست حرارتی | فعال بودن thermald؟ دمای `thermal_zone` زیر بار |
| باتری سریع تمام می‌شود | پروفایل/روشنایی/فرسودگی | `powerprofilesctl get`، سطح روشنایی، `upower -d` (energy_full در برابر design) |

## چیزهایی که نرم‌افزار نمی‌تواند حل کند

* نوفه بلندگو یا میکروفونی که در سطح سخت‌افزار Clip می‌شود.
* دوربین‌هایی با سنسور کم‌کیفیت و فوکوس ثابت.
* فرسودگی باتری (`energy_full` بسیار کمتر از `energy_full_design`).
* محدودیت حرارتی بدنه — Throttling زیر بار ممتد، محافظت firmware از CPU است، نه باگ توزیع.

این موارد را با شواهد به‌عنوان محدودیت سخت‌افزاری گزارش کنید؛ با دستکاری Gain یا فن روی آن‌ها سرپوش نگذارید.
