# APT repositories and mirrors

**English** ([apt-mirrors.md](apt-mirrors.md)) | فارسی ([apt-mirrors.fa.md](apt-mirrors.fa.md))

## What ships in the image

Every Yaran image ships the smallest possible APT configuration:

| Image | Repositories |
|---|---|
| Desktop Standard / ARM64 | `trixie`, `trixie-updates`, `trixie-security` |
| Desktop Minimal / Extended | the three above **plus** `trixie-backports` |
| Server | `trixie`, `trixie-updates`, `trixie-security` |

Rules enforced by `hooks/common/verify-image.sh` at build time (a violation
fails the build):

* no repository may use `trusted=yes`, disabled signature checks or similar
  shortcuts;
* every repository that is not the default Debian archive must pin its origin
  with `signed-by=/usr/share/keyrings/...`;
* `trixie-backports` may only be present together with a package pin that
  justifies it.

## Why Minimal/Extended keep trixie-backports

`telegram-desktop` is **not packaged in trixie main**; it only exists in
`trixie-backports`. `hooks/desktop/vendor-repos.sh` therefore adds a pin:

```
Package: telegram-desktop
Pin: release n=trixie-backports
Pin-Priority: 990
```

so exactly one package is taken from backports and everything else stays on
the stable suites. Removing backports means removing `telegram-desktop` from
those images.

## Vendor repositories (Minimal/Extended, amd64)

| Repository | Needed by | Key handling |
|---|---|---|
| Google Chrome (`dl.google.com`) | `google-chrome-stable` | key stored in `/usr/share/keyrings/google-chrome.asc`, `signed-by` in the source line |
| VirtualBox (Extended only, `download.virtualbox.org`) | `virtualbox-7.2` | key stored in `/usr/share/keyrings/oracle-virtualbox.asc`, `signed-by` in the source line |

Both hooks (`vendor-repos.sh`, `vendor-repos-extended.sh`) refuse to install
anything if the signing key cannot be fetched, and skip gracefully on
non-amd64 hosts.

Adding a vendor repository is an **explicit per-manifest decision**: the
hooks only run when the manifest sets `"vendor_repositories": true`
(forwarded as `YARAN_VENDOR_REPOSITORIES=1`), record every vendor **origin
host** they enabled in `/etc/apt/yaran-vendor-repos`, and
`hooks/common/verify-image.sh` fails the build if any non-Debian source in
`sources.list.d` has no matching opt-in entry. Consent is tracked per host
rather than per filename because a shipped package can register its own
source file for an already-opted-in origin — `google-chrome-stable`'s
postinst writes `/etc/apt/sources.list.d/google-chrome.sources` (deb822) on
a fresh install — and the policy checks the origin, not the file. A manifest
without the flag never adds a vendor repository — the plain Debian suites
are always preserved untouched.

Hiddify and v2rayN do **not** use APT repositories at all: they are pinned
`.deb` files verified against a recorded SHA-256
(`hooks/desktop/install-external-apps.sh`).

## Node.js without an APT repository (Extended)

Debian trixie packages Node.js 20.x only; every external APT repository
that ships a newer major (e.g. NodeSource) is forbidden by the repository
policy above. The Extended image therefore installs the official Node.js
**26.x** release tarball from `nodejs.org` — which bundles `npm` and
`npx` — under `/usr/local/lib/nodejs` via
`hooks/desktop/install-nodejs26.sh`. The download is verified against a
pinned SHA-256 **and** cross-checked against the upstream
`SHASUMS256.txt` before extraction, so a swapped upstream artifact fails
the build. `hooks/common/verify-image.sh` then asserts `node --version`
starts with `v26.` and that `npm` runs.

## Changing the mirror

The default mirror is `http://deb.debian.org/debian`, which redirects to a
nearby mirror automatically. To build against a different trusted mirror,
edit the `apt_mirror` and `apt_sources` keys of the manifest:

```json
"apt_mirror": "https://mirror.example.org/debian",
"apt_sources": [
  "deb https://mirror.example.org/debian trixie main contrib non-free non-free-firmware",
  "deb https://mirror.example.org/debian trixie-updates main contrib non-free non-free-firmware",
  "deb https://security.debian.org/debian-security trixie-security main contrib non-free non-free-firmware"
]
```

Notes:

* the mirror must serve the same suites and carry the standard Debian
  signatures — do not add mirrors that require `trusted=yes`;
* `security.debian.org` should stay the canonical security source (or an
  official security mirror of it);
* on an **installed** system, replacing `/etc/apt/sources.list` with a
  regional mirror (e.g. an Iranian mirror) is a normal user operation and
  needs no image change; `apt update` afterwards must complete without errors
  before reporting the image as working.
