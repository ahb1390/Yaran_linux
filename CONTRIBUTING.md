# Contributing to Yaran Linux

**English** ([CONTRIBUTING.md](CONTRIBUTING.md)) | فارسی ([CONTRIBUTING.fa.md](CONTRIBUTING.fa.md))

Thank you for helping improve Yaran Linux. This guide covers how to propose
changes, what to test before opening a pull request, and how documentation
and translations are maintained.

## Before you start

- Search the [issue tracker](https://github.com/ahb1390/Yaran_linux/issues)
  for existing reports before filing a new one.
- For larger changes (new packages in the base images, new hooks, manifest
  structure changes), open an issue first to discuss scope. Package
  additions should solve a common desktop need, hardware requirement,
  security issue, or accessibility problem; optional specialist
  applications belong in repositories, not the base image.
- Read the [architecture](docs/architecture.md) and
  [manifest](docs/manifest.md) guides so your change fits the design.

## Branch layout

- The default branch is `rebrand/yaran-linux`; feature work happens in
  branches cut from it.
- Create a focused branch per change, e.g. `docs/troubleshooting-fa` or
  `fix/arm64-package-list`.
- Do not push directly to the default branch. Open a pull request instead.

## Making changes

Scope of a typical contribution:

| Change type | Where | Rules |
|---|---|---|
| Packages for an edition | `Yaran-2.0-*.json` manifests | Validate all manifests; keep the set lean; guard architecture-specific additions |
| System configuration | `hooks/desktop/`, `hooks/server/`, `hooks/common/` | Hooks are root code: keep them readable, idempotent where possible, and `set -e` safe |
| Builder behavior | `build.py` | Add or extend unit tests in `tests/`; keep the builder distribution-agnostic — no Yaran branding in code |
| Branding | `assets/` | Follow the [theme guide](docs/theme.md); update it if you add themed surfaces |
| Documentation | `README.md`, `docs/`, `CONTRIBUTING.md` | Update **both** language versions (see below) |

Do not modify `.gitignore`, `LICENSE`, or published workflow behavior
without discussion in an issue.

## Testing before a pull request

Run the same checks CI runs:

```bash
python3 -m unittest discover -s tests -v
for config in Yaran*.json examples/*.json; do
  python3 build.py "$config" --validate
done
find hooks scripts -name '*.sh' -exec bash -n {} \;
```

For changes that affect the built image (manifests, hooks, assets), also do
a real build of the affected edition and boot it in a VM:

```bash
sudo python3 build.py Yaran-2.0-amd64-minimal.json \
  --workdir build-test --outdir output-test
qemu-system-x86_64 -m 4096 -smp 2 -boot d \
  -cdrom output-test/Yaran-2.0-amd64-minimal.iso
```

See the [builder guide](docs/builder.md) for host requirements and the
[troubleshooting guide](docs/troubleshooting.md) when a build fails. The
`RUN_BOOT_SMOKE=1` environment variable additionally runs the QEMU boot
smoke test (needs QEMU, GRUB amd64 modules, and OVMF for the UEFI check).

## Documentation and translations

Every Markdown document exists in two languages:

- English: `README.md`, `docs/builder.md`, `docs/architecture.md`,
  `docs/manifest.md`, `docs/troubleshooting.md`, `docs/releases.md`,
  `docs/theme.md`, `CONTRIBUTING.md`
- Persian: the same names with `.fa.md` (e.g. `docs/builder.fa.md`)

Rules for contributors:

1. A change to an English document must update its `.fa.md` counterpart in
   the same pull request (and vice versa). Translations are complete
   translations, not summaries.
2. Keep commands, file paths, JSON keys, package names, and code blocks
   **identical** across languages — translate the prose, not the syntax.
3. Keep the language switcher line at the top of every document.
4. If you add a new document, add both language versions and link them from
   the README documentation lists.

## Commit messages and pull requests

- Write concise, imperative commit messages
  (`Fix ARM64 package list`, not `fixed the package list`).
- In the pull request description, state what changed and why, which
  manifests or images are affected, and exactly what you tested (commands
  run, ISO booted or not).
- Keep pull requests focused: one concern per PR. Documentation-only
  changes do not need a build, but must pass the validation commands above.

## Reporting bugs

Include, whenever possible:

- the manifest name and the exact command you ran;
- the full error output, including the failing step banner
  (`Running debootstrap`, `Installing packages`, …);
- host distribution, architecture, and `python3 --version`;
- for boot problems: the ISO name, the GRUB entry used, and the last
  messages visible with `live, debug`.

Security-sensitive reports (for example, a weakness in the live image
defaults) should not be filed as public issues; contact the maintainers
directly through GitHub.

## Review process

Pull requests are reviewed for technical correctness (does the change do
what it claims, per the source), image impact (does it bloat or break an
edition), and documentation completeness (both languages updated). A
change is merged only after the Build workflow passes on it.
