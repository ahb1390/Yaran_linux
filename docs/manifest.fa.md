**English** ([manifest.md](manifest.md)) | فارسی ([manifest.fa.md](manifest.fa.md))
# مرجع مانیفست

هر تصویر Yaran Linux با یک مانیفست JSON توصیف می‌شود که توسط `build.py` خوانده و
پردازش می‌گردد. این سند همهٔ فیلدهای پذیرفته‌شده، مقدار پیش‌فرض آن‌ها و قواعد اعتبارسنجی‌شان را دقیقاً مطابق
پیاده‌سازی موجود در builder فهرست می‌کند. کلیدهای ناشناخته رد می‌شوند؛ بنابراین یک تنظیم
غلب‌نویسی‌شده به‌جای ناپدیدشدن بی‌صدا، در اعتبارسنجی شکست می‌خورد.

اعتبارسنجی یک مانیفست بدون دسترسی root و بدون شبکه:

```sh
python3 build.py path/to/manifest.json --validate
```

## مثال حداقلی

```json
{
  "distro_name": "Yaran",
  "version": "2.0",
  "architecture": "amd64",
  "suite": "trixie",
  "apt_mirror": "http://deb.debian.org/debian",
  "apt_components": ["main", "contrib", "non-free", "non-free-firmware"],
  "apt_sources": [
    "deb http://deb.debian.org/debian trixie main contrib non-free non-free-firmware",
    "deb http://deb.debian.org/debian trixie-updates main contrib non-free non-free-firmware",
    "deb http://security.debian.org/debian-security trixie-security main contrib non-free non-free-firmware"
  ],
  "hostname": "yaran",
  "live_username": "admin",
  "live_user_password": "yaranlinux",
  "root_password": null,
  "packages": ["kde-plasma-desktop", "firefox-esr"],
  "pre_chroot_scripts": [],
  "post_install_scripts": [],
  "iso_filename": "Yaran-example.iso",
  "iso_volume_id": "YARAN_EXAMPLE"
}
```

## فیلدهای الزامی

| کلید | نوع | قواعد |
|---|---|---|
| `distro_name` | رشته | غیرخالی و تک‌خطی؛ بدون کاراکترهای `"` `\` `` ` `` `$` `;` `{` `}` (این کاراکترها در نهایت وارد پیکربندی بوت می‌شوند) |
| `version` | رشته | همان قواعد `distro_name` |
| `suite` | رشته | نسخهٔ upstream در `debootstrap`؛ برای نمونه `trixie` یا `noble` |
| `apt_mirror` | رشته | URL میرور بوت‌استرپ |
| `packages` | فهرست | نام بسته‌ها (`[a-z0-9][a-z0-9+.:_-]*`)؛ می‌تواند خالی باشد |

## هویت و معماری

| کلید | مقدار پیش‌فرض | توضیحات |
|---|---|---|
| `architecture` | `amd64` | یکی از `amd64`، `arm64`، `armhf`. باید با خروجی `dpkg --print-architecture` میزبان سازگار باشد |
| `hostname` | slug حاصل از `distro_name` | یک برچسب DNS معتبر، حداکثر ۶۳ نویسه |
| `kernel_package` | متاپکیج Debian متناسب با معماری (`linux-image-amd64`، `linux-image-arm64`، `linux-image-armmp`) | برای مشتق‌شده‌ها قابل بازنویسی است |
| `iso_filename` | `<slug>-<version>-<arch>.iso` | باید یک نام فایل `.iso` ساده باشد: `[A-Za-z0-9][A-Za-z0-9_.-]*\.iso`. اگر فایلی با همین نام از قبل وجود داشته باشد، در زمان ساخت رد می‌شود |
| `iso_volume_id` | `distro_name` با حروف بزرگ | ۱ تا ۳۲ حرف، رقم یا underscore؛ به برچسب volume ISO تبدیل می‌شود و کلید جستجوی اصلی GRUB خواهد بود |

نام‌های مستعار قدیمی `arch` (برای `architecture`) و `debian_distro` (برای `suite`)
همچنان پشتیبانی می‌شوند؛ جفت‌های ناسازگار از نام مستعار قدیمی و کلید جدید رد می‌شوند.

## پیکربندی APT

| کلید | مقدار پیش‌فرض | توضیحات |
|---|---|---|
| `apt_components` | `["main"]` | به `debootstrap` نیز پاس داده می‌شود؛ باید غیرخالی باشد |
| `apt_sources` | یک خط `deb` ساخته‌شده از mirror/suite/components | خطوط source کامل. **هیچ مخزن security/updates ضمنی وجود ندارد** — هر مخزنی را که می‌خواهید فهرست کنید، از جمله updates، security، backports و مخازن شخص ثالث |
| `install_recommends` | `false` | هم بر شبیه‌سازی APT و هم بر نصب واقعی اثر می‌گذارد |
| `vendor_repositories` | `false` | اجازهٔ صریح برای افزودن مخازن APT **غیر Debian** به `/etc/apt/sources.list.d/` توسط هوک‌ها. بدون این کلید، هر هوک `pre_chroot_scripts` که بستهٔ فروشنده (Google Chrome، VirtualBox و…) داشته باشد در اعتبارسنجی رد می‌شود و `hooks/common/verify-image.sh` اگر منبع فروشنده‌ای خارج از این مجوز بیابد، ساخت را متوقف می‌کند. به‌صورت `YARAN_VENDOR_REPOSITORIES=1` به هوک‌ها منتقل می‌شود |
| `exclude_packages` | `[]` | به‌صورت pinهای منفی APT نصب می‌شوند که از انتخاب‌شدن بسته‌ها جلوگیری می‌کنند؛ نباید با بسته‌هایی که صریحاً درخواست شده‌اند هم‌پوشانی داشته باشد |
| `debootstrap_variant` | حذف‌شده | معمولاً `minbase` یا `buildd` |
| `debootstrap_script`، `debootstrap_keyring` | حذف‌شده | مسیرهای موجود روی میزبان (نسبی به مانیفست یا مطلق) برای انتخاب یک `suite` اسکریپت سفارشی یا keyring امضای سفارشی |

از آنجا که یک توزیع مشتق‌شده مخازن Debian را به‌صورت خودکار به ارث نمی‌برد،
`apt_sources` باید کامل باشد: برای نمونه، یک مانیفست مبتنی بر Ubuntu اگر بروزرسانی می‌خواهد،
به خط updates مخصوصِ خودش نیاز دارد.

## سیستم زنده (Live)

| کلید | مقدار پیش‌فرض | توضیحات |
|---|---|---|
| `live_username` | `user` | نام حساب کاربری معتبرِ غیر root، یا `null` برای ردکردن ساخت کاربر زنده |
| `live_user_password`، `root_password` | `null` | مقدار `null` احراز هویت با گذرواژه را قفل می‌کند؛ رشتهٔ خالی حساب را حذف می‌کند؛ هر رشتهٔ دیگری همان گذرواژه را تنظیم می‌کند |
| `user_groups` | `sudo`، `audio`، `video`، `plugdev`، `netdev` | گروه‌های کاربر زنده |
| `live_packages` | `live-boot`، `live-config`، `live-config-systemd`، `live-boot-initramfs-tools`، `initramfs-tools`، `tzdata`، `systemd-sysv`، `sudo`، `locales` | ارائهٔ این کلید **کل فهرست پیش‌فرض را جایگزین می‌کند** |
| `locale`، `timezone` | `en_US.UTF-8`، `UTC` | مسیر منطقهٔ زمانی نسبت به دایرکتوری zoneinfo است (برای نمونه `Asia/Tehran`) |
| `boot_append` | `quiet` | آرگومان‌های kernel برای ورودی‌های زنده؛ همان محدودیت‌های کاراکتریِ `distro_name`. افزودن `noautologin` ورود خودکار نشست زنده را غیرفعال می‌کند |
| `squashfs_compression` | `xz` | در صورت پشتیبانی ابزارهای میزبان و kernel مقصد، `zstd`، `gzip`، `lzo` و `lz4` نیز مجاز هستند |
| `services` | `{"enable": [], "disable": [], "mask": []}` | unitهای systemd؛ هر شکستی ساخت را متوقف می‌کند |
| `os_release` | `{}` | بازنویسی فیلدها با حروف بزرگ که با `/usr/lib/os-release` ادغام می‌شود؛ فیلدهای upstream که مشخص نشده‌اند دست‌نخورده باقی می‌مانند |

گذرواژه‌های `null` احراز هویت با گذرواژه را قفل می‌کنند؛ اما ورود خودکار نشست زنده و پیکربندی `sudo` را غیرفعال نمی‌کنند. مانیفست‌های Yaran Linux گذرواژه‌های زندهٔ منتشرشدهٔ خود را حفظ می‌کنند (`admin` / `yaranlinux`). هرگز از این مقادیر پیش‌فرض برای یک سیستم نصب‌شدهٔ عملیاتی استفاده نکنید.

کلید قدیمی و بلااستفادهٔ `splash` باید با `boot_append` جایگزین شود؛ کلید قدیمی
`security_mirror` نیز باید با `apt_sources` صریح جایگزین گردد.

## هوک‌ها

| کلید | مقدار پیش‌فرض | توضیحات |
|---|---|---|
| `pre_chroot_scripts` | `[]` | هوک‌های میزبان که پس از بوت‌استرپ و پیش از نخستین بروزرسانی APT اجرا می‌شوند؛ متغیر `$ROOTFS` به chroot اشاره می‌کند |
| `post_install_scripts` | `[]` | هوک‌های chroot که پس از نصب بسته‌ها، کاربران و پیکربندی سیستم اجرا می‌شوند |

می‌توانید در هر ورودی مسیرها (نسبی به مانیفست) یا اسکریپت‌های درون‌خطی قرار دهید. هوک‌ها با
Bash و با پرچم `-eu` و با دسترسی root اجرا می‌شوند و کد مورد اعتماد به‌شمار می‌روند. برای
پیکربندی‌های رایج از `services` و `os_release` استفاده کنید و هوک‌ها را برای فایل‌ها و
برنامه‌های ویژهٔ توزیع خود نگه دارید. ترتیب دقیق اجرا را در [معماری](architecture.fa.md#هوک‌ها-پیش-از-chroot-در-برابر-پس-از-نصب)
ببینید.

## منوی بوت

| کلید | مقدار پیش‌فرض | توضیحات |
|---|---|---|
| `grub_menu` | مقادیر پیش‌فرض تولیدشده | شیء‌ای که می‌تواند شامل `timeout`، `default`، `background` و/یا `entries` باشد |
| `grub_background` | حذف‌شده | مسیر پس‌زمینهٔ سطح‌بالای قدیمی؛ ترجیح با `grub_menu.background` است |

- مقدار `background` مسیر یک فایل PNG/JPG/TGA **نسبت به دایرکتوری مانیفست** است.
  با پیکربندی آن، terminal گرافیکی GRUB فعال می‌شود و ماژول‌های تصویری لازم در ISO تعبیه می‌گردند.
- مقدار `entries` فهرستی از ورودی‌های منو با فیلدهای `title`، `linux`، `initrd` و
  `parameters` (اختیاری) است؛ مسیرهای kernel/initrd **نسبت به ریشهٔ ISO**
  هستند (برای نمونه `/live/vmlinuz`). با حذف `entries`، ورودی‌های تولیدشدهٔ
  `live`، `live, nomodeset` و `live, debug` حفظ می‌شوند.

## مانیفست‌های Yaran Linux

| مانیفست | نسخه | توضیحات |
|---|---|---|
| `Yaran-2.0-amd64-minimal.json` | Desktop Minimal | دسکتاپ KDE Plasma پایه + Calamares |
| `Yaran-2.0-amd64-extended.json` | Desktop Extended | GIMP، VirtualBox، VSCodium، Obsidian و زنجیرهٔ ابزار توسعه را اضافه می‌کند |
| `Yaran-2.0-arm64.json` | Desktop ARM64 | برنامه‌های ویژهٔ AMD64 را حذف می‌کند |
| `Yaran-Server-2.0-amd64.json` | Server | بدون رابط گرافیکی؛ نصب‌کنندهٔ CLI؛ SSH در رسانهٔ زنده غیرفعال است |
| `Yaran-2.0-amd64.json` | دسکتاپ قدیمی | برای حفظ سازگاری نگه داشته شده؛ توسط CI ساخته نمی‌شود |

## افزودن ایمن بسته‌ها

1. **به بسته‌های Debian اولویت دهید.** هر چیزی که در `packages` می‌آورید باید در `suite`
   و `component`هایی که پیکربندی کرده‌اید موجود باشد. ابتدا اعتبارسنجی کنید، سپس با یک ساخت
   واقعی بررسی نمایید — اعتبارسنجی مخازن ازرا دور را استعلام نمی‌کند.
2. **مخازن APT شخص ثالث** باید در یک هوک `pre_chroot_scripts` قرار بگیرند که یک
   source **امضاشده** می‌سازد: کلید امضای فروشنده را از طریق HTTPS دریافت کنید، آن را در
   `/usr/share/keyrings/` (یا معادل مرحله‌بندی‌شده) ذخیره کنید و در خط source با `signed-by=`
   به آن ارجاع دهید — دقیقاً همان‌طور که `hooks/desktop/vendor-repos.sh` برای Google Chrome
   انجام می‌دهد. اعتبارسنجی امضا را غیرفعال نکنید؛ builder هیچ مسیر دور زدنی فراهم نمی‌کند.
3. **فایل‌های `.deb` شخص ثالث بدون مخزن** باید از الگوی `hooks/desktop/install-external-apps.sh`
   پیروی کنند: نسخهٔ رسمی دقیق را با URL مشخص سازگار کنید، دانلود را با یک مقدار ثبت‌شدهٔ
   SHA-256 راستی‌آزمایی کنید و سپس با `apt-get install ./file.deb` نصب نمایید، تا APT
   وابستگی‌ها را از مخازن پیکربندی‌شدهٔ شما حل کند.
4. **افزودنی‌های ویژهٔ معماری** باید شرطی شوند. هوک‌های فروشنده در این مخزن
   `dpkg --print-architecture` را بررسی می‌کنند و روی معماری‌های دیگر به‌صورت تمیز
   skip می‌شوند؛ همین موضوع ساخت‌پذیری تصویر ARM64 را ممکن می‌کند. هرگز یک بستهٔ
   ویژهٔ amd64 را بدون چنین شرطی به فهرست مشترک اضافه نکنید.
5. **مجموعه را تُنگ نگه دارید.** افزودن بسته باید یک نیاز رایج، نیازمندی سخت‌افزاری،
   مسئلهٔ امنیتی یا مشکل دسترس‌پذیری را حل کند.
