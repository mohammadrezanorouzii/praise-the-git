# Praise the Git &nbsp; \\[T]/

*— Prepare to Push Edition —*

A Dark Souls style banner for your terminal: when `git push` succeeds you get
a golden **CODE PUSHED** across the screen — complete with the metallic
gradient, a sweeping sheen, fade in/out, a solemn chime, and a souls counter
(your total commit count). When the push fails, you get the blood-red
**YOU DIED**.

More git moments are covered too:

| git command                  | outcome  | banner                                |
| ---------------------------- | -------- | ------------------------------------- |
| `git push`                   | success  | **CODE PUSHED** (gold, souls counter) |
| `git push`                   | failure  | **YOU DIED** (red)                    |
| `git merge` / `git rebase`   | success  | **VICTORY ACHIEVED** (gold, souls)    |
| `git merge` / `git rebase`   | conflict | **YOU DIED** (red)                    |
| `git checkout -b` / `switch -c` | new branch | its name as a silver area-name banner, like entering a new zone |
| `git stash`                  | stashed  | **HUMANITY RESTORED** (silver)        |

(`--abort`/`--quit` calls and a `git stash` that had nothing to save stay
silent; the git exit code is always preserved.)

Inspired by the "Email Sent" Dark Souls browser extension, rebuilt for the
terminal. Works on Linux, macOS, and Windows 10+ (cmd / Windows Terminal).

## How it looks

The text is rendered with Cinzel (the free Trajan-style typeface — the same
letterform family Dark Souls uses), rasterized with antialiasing and drawn
using quadrant block characters (`▀▌▞▟`…), which gives a 2x2 grid of pixels
per terminal cell. Needs a truecolor terminal (any modern one).

## Install

### Linux / macOS

```sh
./install.sh
```

Then restart your shell (or `source ~/.bashrc` / `source ~/.zshrc`) and run
`praise-test` to preview. The installer:

- installs the `praise` command (via `pipx` if present, else
  `pip install --user`, else a symlink that runs from this checkout), and
- adds one guarded `source` line to your `~/.bashrc` and/or `~/.zshrc` that
  loads the `git push` wrapper.

### Windows (cmd)

```bat
install.bat
```

This pip-installs the `praise` command and drops `gitpush.cmd` into your
per-user Scripts directory. In cmd, use **`gitpush`** instead of `git push`:

```bat
gitpush origin main
```

(cmd has no shell functions, so plain `git push` can't be wrapped the way it
is on Linux/macOS — `gitpush` runs the real push and shows the banner based
on its exit code. Everything works in both classic cmd and Windows Terminal;
ANSI colors are enabled automatically.)

### Any platform, manually

```sh
pip install .        # or: pipx install .
praise          # try it
```

## Usage

On Linux/macOS the banners fire automatically on the git commands in the
table above (via a shell wrapper function, so interactive shells only —
scripts and non-interactive shells are unaffected). Preview any time with
`praise-test [fail|victory|branch|stash]` (nothing touches git state).

The renderer is a general-purpose command you can use for anything:

```sh
praise                       # "CODE PUSHED", gold
praise "BONFIRE LIT"         # any text
praise --red "YOU DIED"      # red theme
praise --theme silver "UNDEAD BURG"   # gold / red / silver
praise --souls 1247 "CODE PUSHED"     # souls counter under the banner
praise --no-sound "QUIET"    # skip the chime
praise --dump "TEST"         # print one static frame (no animation)
praise --png out.png "TEST"  # render a frame to an image
```

## Requirements

- Python 3.8+ (Pillow is installed automatically with the package; without
  it the banner falls back to a low-res built-in bitmap font)
- A truecolor terminal (any modern terminal; on Windows 10+ VT processing
  is enabled automatically)
- Sound is built in: `winsound` on Windows, `afplay` on macOS,
  `paplay`/`aplay`/`ffplay` on Linux — whichever exists; silence otherwise

## Sound

A synthesized chord swell is generated on first run into the app's data
directory (`~/.local/share/praise-the-git` on Linux,
`~/Library/Application Support/praise-the-git` on macOS,
`%LOCALAPPDATA%\praise-the-git` on Windows). Replace `chime.wav` there with any
`.wav` (e.g. the real "Victory Achieved" sound) to use your own.

## Project layout

```
src/cli.py                       # the whole program: rasterizer, renderer, animation, sound
src/assets/                      # Cinzel.ttf (OFL licensed, from Google Fonts)
praise                           # launcher to run from the repo without installing
shell/git-banner.sh              # git() wrapper + praise-test (bash/zsh)
shell/gitpush.cmd                # Windows cmd shim
install.sh / install.bat         # per-platform installers, idempotent
pyproject.toml                   # pip/pipx packaging
```

## Uninstall

- Linux/macOS: remove the `# >>> praise-the-git ... <<<` block from your rc
  file(s), then `pipx uninstall praise-the-git` (or `pip uninstall`, or
  delete the `~/.local/bin/praise` symlink), and delete the data dir.
- Windows: `pip uninstall praise-the-git` and delete `gitpush.cmd` from
  your Scripts directory.

## License

Code: MIT. The bundled Cinzel font is licensed under the SIL Open Font
License 1.1 (https://openfontlicense.org), © The Cinzel Project Authors.
