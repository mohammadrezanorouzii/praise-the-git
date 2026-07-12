# darksouls-gitpush

A Dark Souls style banner for your terminal: when `git push` succeeds you get
a golden **CODE PUSHED** across the screen — complete with the metallic
gradient, a sweeping sheen, fade in/out, and a solemn chime. When the push
fails, you get the blood-red **YOU DIED**.

Inspired by the "Email Sent" Dark Souls browser extension, rebuilt for the
terminal. Works on Linux, macOS, and Windows 10+ (cmd / Windows Terminal).

## How it looks

The text is rendered with Cinzel (the free Trajan-style typeface — the same
letterform family Dark Souls uses), rasterized with antialiasing and drawn
using half-block characters (`▀`), which gives two independently colored
pixels per terminal cell. Needs a truecolor terminal (any modern one).

## Install

### Linux / macOS

```sh
./install.sh
```

Then restart your shell (or `source ~/.bashrc` / `source ~/.zshrc`) and run
`gitpush-test` to preview. The installer:

- installs the `code-pushed` command (via `pipx` if present, else
  `pip install --user`, else a symlink that runs from this checkout), and
- adds one guarded `source` line to your `~/.bashrc` and/or `~/.zshrc` that
  loads the `git push` wrapper.

### Windows (cmd)

```bat
install.bat
```

This pip-installs the `code-pushed` command and drops `gitpush.cmd` into your
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
code-pushed          # try it
```

## Usage

On Linux/macOS the banner fires automatically on `git push` (via a shell
wrapper function, so real pushes only — scripts and non-interactive shells
are unaffected). Preview any time with `gitpush-test` / `gitpush-test fail`
(nothing is pushed; git isn't even called).

The renderer is a general-purpose command you can use for anything:

```sh
code-pushed                       # "CODE PUSHED", gold
code-pushed "BONFIRE LIT"         # any text
code-pushed --red "YOU DIED"      # red theme
code-pushed --no-sound "QUIET"    # skip the chime
code-pushed --dump "TEST"         # print one static frame (no animation)
code-pushed --png out.png "TEST"  # render a frame to an image
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
directory (`~/.local/share/code-pushed` on Linux,
`~/Library/Application Support/code-pushed` on macOS,
`%LOCALAPPDATA%\code-pushed` on Windows). Replace `chime.wav` there with any
`.wav` (e.g. the real "Victory Achieved" sound) to use your own.

## Project layout

```
src/cli.py                       # the whole program: rasterizer, renderer, animation, sound
src/assets/                      # Cinzel.ttf (OFL licensed, from Google Fonts)
code-pushed                      # launcher to run from the repo without installing
shell/git-banner.sh              # git() wrapper + gitpush-test (bash/zsh)
shell/gitpush.cmd                # Windows cmd shim
install.sh / install.bat         # per-platform installers, idempotent
pyproject.toml                   # pip/pipx packaging
```

## Uninstall

- Linux/macOS: remove the `# >>> code-pushed ... <<<` block from your rc
  file(s), then `pipx uninstall darksouls-gitpush` (or `pip uninstall`, or
  delete the `~/.local/bin/code-pushed` symlink), and delete the data dir.
- Windows: `pip uninstall darksouls-gitpush` and delete `gitpush.cmd` from
  your Scripts directory.

## License

Code: MIT. The bundled Cinzel font is licensed under the SIL Open Font
License 1.1 (https://openfontlicense.org), © The Cinzel Project Authors.
