# Bash experience

**English** ([bash-experience.md](bash-experience.md)) | فارسی ([bash-experience.fa.md](bash-experience.fa.md))

Yaran Linux ships an enhanced interactive Bash: menu completion, history
suggestions, syntax highlighting, a colored prompt with the git branch, and
sane history/alias defaults — without changing anyone's login shell.

## What is installed where

| Component | Package / file | Editions |
|---|---|---|
| Completion framework | `bash-completion` (Debian) | all images |
| Experience config | `/usr/share/yaran/bash/yaran-bashrc`, sourced from `/etc/bash.bashrc` | all images |
| ble.sh v0.4.0-devel3 (BSD-3-Clause, pinned SHA-256) | `/usr/share/ble.sh` via `hooks/common/install-ble.sh` | desktop images only |

The server image gets completion, history, colors and the git prompt but
not ble.sh — servers keep a plain, predictable shell.

## How it reaches users

Debian's bash reads `/etc/bash.bashrc` for **every** interactive shell, so
the config covers the live session, users created by Calamares and existing
users. Personal `~/.bashrc` files are never rewritten and still load
afterwards, so anything a user configured keeps winning. Non-interactive
shells and scripts are untouched (verified by tests).

## Features

* **Tab = menu completion** (ble.sh): candidates in a readable menu,
  arrow/Tab navigation, files colored by type, git/apt/tool completions.
* **History suggestions**: the best match from history appears dimmed while
  you type; it is inserted into the line and executed only when you press
  Enter — nothing runs by itself.
* **Prompt**: `user@host ~/path (branch*) $` — branch from Debian's own
  `git-prompt` (`*` staged, `+` unstaged, `$` stash, `%` untracked,
  ahead/behind markers); a subtle `[n]` shows a non-zero exit code and
  disappears after a successful command.
* **Colors**: Yaran green/teal, degrading to 8-color or plain on limited
  terminals; colored `ls`/`grep`/`diff` and man page emphasis.
* **History**: 100k entries, appended across shells (no last-writer-wins),
  duplicates dropped, blank-prefixed commands skipped (type ` cmd` with a
  leading space to keep a password argument out of the history).

## Failure behaviour

If ble.sh is missing or fails to load, the shell still starts with the
prompt, colors, history and Debian `bash-completion`. There is no network
access at shell startup; ble.sh is fetched once at image build time,
checksum-verified, and recorded in `/usr/share/ble.sh/yaran-provenance`.

## Measured performance (this machine, i5-4200M)

| Shell | First prompt |
|---|---|
| base config, no ble.sh | 16–25 ms |
| with ble.sh | ~250 ms (first load), faster once cached |

## Opting out

```bash
# in ~/.bashrc, after /etc/bash.bashrc has run:
# disable only the ble.sh part
YARAN_BLE_SH=/nonexistent
```
or `unset PROMPT_COMMAND` / redefine `PS1` to return to a plain prompt.
