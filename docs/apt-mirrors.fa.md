# مخازن APT و Mirrorها

**English** ([apt-mirrors.md](apt-mirrors.md)) | فارسی ([apt-mirrors.fa.md](apt-mirrors.fa.md))

## چه چیزی داخل تصویر قرار دارد

هر تصویر یاران کوچک‌ترین پیکربندی ممکن APT را دارد:

| تصویر | مخازن |
|---|---|
| دسکتاپ استاندارد / ARM64 | `trixie` ، `trixie-updates` ، `trixie-security` |
| دسکتاپ مینیمال / Extended | سه مورد بالا **به‌علاوه** `trixie-backports` |
| سرور | `trixie` ، `trixie-updates` ، `trixie-security` |

قواعدی که `hooks/common/verify-image.sh` در زمان ساخت بررسی می‌کند (هر نقضی ساخت را متوقف می‌کند):

* هیچ مخزنی نباید از `trusted=yes`، غیرفعال‌کردن تأیید امضا یا میان‌برهای مشابه استفاده کند؛
* هر مخزنی غیر از آرشیو پیش‌فرض Debian باید با `signed-by=/usr/share/keyrings/...` مبدأ خود را پین کند؛
* `trixie-backports` فقط باید همراه با Pin بسته‌ای که وجودش را توجیه می‌کند باشد.

## چرا مینیمال/Extended تریکسی-بکپورت را نگه می‌دارند

بسته‌ی `telegram-desktop` در `trixie main` وجود **ندارد**؛ فقط در `trixie-backports` عرضه می‌شود. به همین دلیل `hooks/desktop/vendor-repos.sh` این Pin را اضافه می‌کند:

```
Package: telegram-desktop
Pin: release n=trixie-backports
Pin-Priority: 990
```

بنابراین فقط یک بسته از بکپورت می‌آید و بقیه روی Suiteهای پایدار می‌مانند. حذف بکپورت یعنی حذف `telegram-desktop` از این تصاویر.

## مخازن جانبی (مینیمال/Extended، amd64)

| مخزن | برای چه بسته‌ای | مدیریت کلید |
|---|---|---|
| Google Chrome (`dl.google.com`) | `google-chrome-stable` | کلید در `/usr/share/keyrings/google-chrome.asc` و `signed-by` در خط منبع |
| VirtualBox (فقط Extended، `download.virtualbox.org`) | `virtualbox-7.2` | کلید در `/usr/share/keyrings/oracle-virtualbox.asc` و `signed-by` در خط منبع |

هر دو هوک (`vendor-repos.sh` و `vendor-repos-extended.sh`) اگر نتوانند کلید امضا را دریافت کنند، چیزی نصب نمی‌کنند و روی میزبان‌های غیر amd64 به‌صورت امن رد می‌شوند.

افزودن مخزن فروشنده یک **تصمیم صریح و مجزا برای هر مانیفست** است: هوک‌ها تنها زمانی اجرا می‌شوند که مانیفست `"vendor_repositories": true` داشته باشد (که به‌صورت `YARAN_VENDOR_REPOSITORIES=1` منتقل می‌شود)، هر **میزبان مبدأ** فروشندهٔ فعال‌شده را در `/etc/apt/yaran-vendor-repos` ثبت می‌کنند و `hooks/common/verify-image.sh` اگر منبع غیر Debian در `sources.list.d` بدون ورودی مجوز مطابق پیدا شود، ساخت را متوقف می‌کند. مجوز بر اساس میزبان (نه نام فایل) ثبت می‌شود، چون خودِ یک بستهٔ نصب‌شده می‌تواند برای همان مبدأی که قبلاً مجوز گرفته، فایل منبع خودش را بسازد — postinst بستهٔ `google-chrome-stable` در یک نصب تازه فایل `/etc/apt/sources.list.d/google-chrome.sources` (فرمت deb822) را می‌سازد — و سیاست، مبدأ را بررسی می‌کند نه فایل را. مانیفست بدون این کلید هرگز مخزن فروشنده اضافه نمی‌کند — Suiteهای رسمی Debian همیشه دست‌نخورده حفظ می‌شوند.

Hiddify و v2rayN اصلاً از مخزن APT استفاده نمی‌کنند: فایل `.deb` با نسخه و SHA-256 پین‌شده نصب می‌شوند (`hooks/desktop/install-external-apps.sh`).

## Node.js بدون مخزن APT (Extended)

Debian trixie فقط Node.js نسخهٔ ۲۰ را بسته‌بندی می‌کند؛ هر مخزن APT شخص ثالثی که ماژور جدیدتر داشته باشد (مثلاً NodeSource) طبق سیاست بالا ممنوع است. بنابراین تصویر Extended تاربال رسمی **Node.js 26.x** را از `nodejs.org` — که `npm` و `npx` را همراه دارد — از طریق `hooks/desktop/install-nodejs26.sh` در `/usr/local/lib/nodejs` نصب می‌کند. دانلود با یک SHA-256 پین‌شده تأیید **و** با `SHASUMS256.txt` رسمی upstream تطبیق داده می‌شود، بنابراین جایگزین‌شدن فایل upstream ساخت را با شکست مواجه می‌کند. سپس `hooks/common/verify-image.sh` بررسی می‌کند که `node --version` با `v26.` شروع شود و `npm` هم اجرا شود.

## تغییر Mirror

Mirror پیش‌فرض `http://deb.debian.org/debian` است که به‌صورت خودکار به نزدیک‌ترین Mirror هدایت می‌کند. برای ساخت با یک Mirror معتبر دیگر، کلیدهای `apt_mirror` و `apt_sources` مانیفست را ویرایش کنید:

```json
"apt_mirror": "https://mirror.example.org/debian",
"apt_sources": [
  "deb https://mirror.example.org/debian trixie main contrib non-free non-free-firmware",
  "deb https://mirror.example.org/debian trixie-updates main contrib non-free non-free-firmware",
  "deb https://security.debian.org/debian-security trixie-security main contrib non-free non-free-firmware"
]
```

نکته‌ها:

* Mirror باید همان Suiteها را سرو کند و امضاهای استاندارد Debian را داشته باشد — مخازنی که نیاز به `trusted=yes` دارند اضافه نکنید؛
* `security.debian.org` باید منبع امنیتی معیار باشد (یا یک Mirror رسمی امنیتی از آن)؛
* در یک سیستم **نصب‌شده**، جایگزینی `/etc/apt/sources.list` با یک Mirror منطقه‌ای (مثلاً Mirrorهای ایران) یک عمل عادی کاربر است و نیازی به تغییر تصویر ندارد؛ بعد از آن `apt update` باید بدون خطا کامل شود.
