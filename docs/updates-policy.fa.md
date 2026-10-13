# سیاست به‌روزرسانی (تصاویر دسکتاپ)

**English** ([updates-policy.md](updates-policy.md)) | فارسی ([updates-policy.fa.md](updates-policy.fa.md))

## مشکلی که این سیاست حل می‌کند

مجموعه به‌روزرسانی خودکار Debian در لحظات غیرقابل‌پیش‌بینی قفل‌های APT/DPKG را در دست می‌گیرد:

* `apt-daily.timer` و `apt-daily-upgrade.timer` از نوع `Persistent` هستند؛ بنابراین در **اولین بوت پس از نصب** تقریباً بلافاصله اجرا می‌شوند؛
* سپس `unattended-upgrade` بسته‌ها را دانلود و **نصب** می‌کند، درست وقتی کاربر دارد `apt update` یا `apt install` می‌زند، و پیام
  `Could not get lock /var/lib/dpkg/lock-frontend ... another process uses it` نمایش داده می‌شود؛
* کشتن فرایند یا حذف فایل‌های Lock پایگاه‌داده dpkg را خراب می‌کند و هرگز راه‌حل پذیرفتنی نیست.

## پیش‌فرض تصاویر دسکتاپ یاران

در تصاویر دسکتاپ، **تمام فعالیت‌های پس‌زمینه‌ی APT غیرفعال** هستند:

| تنظیم | مقدار | محل |
|---|---|---|
| `APT::Periodic::Update-Package-Lists` | `"0"` | `/etc/apt/apt.conf.d/20auto-upgrades` |
| `APT::Periodic::Unattended-Upgrade` | `"0"` | همان فایل |
| `apt-daily.timer` | غیرفعال | systemd |
| `apt-daily-upgrade.timer` | غیرفعال | systemd |
| `unattended-upgrades.service` | غیرفعال | systemd |

هیچ‌چیز در تصویر بدون خواسته‌ی کاربر به قفل‌های بسته‌ دست نمی‌زند.

## کاربر چگونه به‌روزرسانی می‌کند

یک ابزار واحد، هم از منوی برنامه‌ها («به‌روزرسانی یاران») و هم از ترمینال:

```bash
yaran-update
```

این فرمان `apt update`، سپس `apt upgrade` تعاملی را اجرا می‌کند (Ctrl+C همیشه امن است) و در پایان `autoremove` را پیشنهاد می‌دهد. به‌روزرسانی‌های امنیتی `trixie-security` بخشی از همین جریان هستند — هرگز حذف نمی‌شوند، فقط بدون اطلاع کاربر نصب نمی‌شوند.

## فعال‌سازی مجدد به‌روزرسانی امنیتی خودکار (اختیاری)

کاربرانی که به‌روزرسانی امنیتی کاملاً خودکار را ترجیح می‌دهند، می‌توانند رفتار Debian را برگردانند:

```bash
sudo systemctl enable --now apt-daily.timer apt-daily-upgrade.timer
sudo tee /etc/apt/apt.conf.d/20auto-upgrades >/dev/null <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
```

بسته‌ی `unattended-upgrades` عمداً در تصویر باقی می‌ماند تا بازگشت به این حالت فقط یک تغییر پیکربندی باشد، نه نصب بسته.

## تصاویر سرور

تصاویر سرور به‌روزرسانی امنیتی خودکار (`trixie-security` فقط) را حفظ می‌کنند — این انتظار متعارف برای سرور بدون حضور کاربر است و سرور نشست دسکتاپی ندارد که با قفل‌ها رقابت کند. `hooks/server/automatic-updates.sh` را ببینید.
