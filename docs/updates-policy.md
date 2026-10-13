# Update policy (desktop images)

**English** ([updates-policy.md](updates-policy.md)) | فارسی ([updates-policy.fa.md](updates-policy.fa.md))

## The problem this policy solves

Debian's automatic update stack takes the APT/DPKG locks at unpredictable
moments:

* `apt-daily.timer` and `apt-daily-upgrade.timer` are `Persistent`, so on the
  very first boot after installation they fire almost immediately;
* `unattended-upgrade` then downloads and *installs* upgrades while the user
  is trying to run `apt update` or `apt install`, producing
  `Could not get lock /var/lib/dpkg/lock-frontend ... another process uses it`;
* killing the process or deleting lock files corrupts the dpkg database and is
  never an acceptable fix.

## Yaran desktop default

The desktop images ship with **all background APT activity disabled**:

| Setting | Value | Where |
|---|---|---|
| `APT::Periodic::Update-Package-Lists` | `"0"` | `/etc/apt/apt.conf.d/20auto-upgrades` |
| `APT::Periodic::Unattended-Upgrade` | `"0"` | same file |
| `apt-daily.timer` | disabled | systemd |
| `apt-daily-upgrade.timer` | disabled | systemd |
| `unattended-upgrades.service` | disabled | systemd |

Nothing in the image touches the package locks unless the user asks for it.

## How users update

One helper does everything, from the application menu ("Yaran Updater") or a
terminal:

```bash
yaran-update
```

It runs `apt update`, then an interactive `apt upgrade` (Ctrl+C is always
safe), and offers an `autoremove` at the end. Security updates from
`trixie-security` are part of this flow — they are never silently skipped,
they are simply never installed behind the user's back.

## Re-enabling automatic security updates (optional)

Users who prefer fully automatic security updates can restore Debian
behaviour:

```bash
sudo systemctl enable --now apt-daily.timer apt-daily-upgrade.timer
sudo tee /etc/apt/apt.conf.d/20auto-upgrades >/dev/null <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
```

`unattended-upgrades` remains installed in the image precisely so this stays a
configuration change, not a package install.

## Server images

Server images keep automatic unattended **security** upgrades enabled
(`trixie-security` only) — that is the conventional expectation for an
unattended server, and the server has no desktop session competing for the
locks. See `hooks/server/automatic-updates.sh`.
