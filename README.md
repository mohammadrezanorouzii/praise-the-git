# darksouls-gitpush

A Dark Souls style banner for your terminal: when `git push` succeeds you get
a golden **CODE PUSHED** across the screen — complete with the metallic
gradient, a sweeping sheen, fade in/out, and a solemn chime. When the push
fails, you get the blood-red **YOU DIED**.

Inspired by the "Email Sent" Dark Souls browser extension, rebuilt for the
terminal.

## How it looks

The text is rendered with Cinzel (the free Trajan-style typeface — the same
letterform family Dark Souls uses), rasterized with antialiasing and drawn
using half-block characters (`▀`), which gives two independently colored
pixels per terminal cell. Needs a truecolor terminal (any modern one).

## Requirements

- Python 3 (no packages needed; `Pillow` recommended — without it the banner
  falls back to a low-res built-in bitmap font)
- A truecolor terminal (`COLORTERM=truecolor`)
- Optional, for sound: `paplay`, `aplay`, or `ffplay`

## Install

```sh
./install.sh
source ~/.bashrc
gitpush-test        # preview the success banner (nothing is pushed)
gitpush-test fail   # preview the failure banner
```

The installer symlinks `code-pushed` into `~/.local/bin` and adds one
`source` line to your `~/.bashrc` (guarded by markers, safe to re-run).

## Usage

The banner fires automatically on `git push` (via a shell wrapper function,
so real pushes only — scripts and non-interactive shells are unaffected).

The renderer is a general-purpose command you can use for anything:

```sh
code-pushed                       # "CODE PUSHED", gold
code-pushed "BONFIRE LIT"         # any text
code-pushed --red "YOU DIED"      # red theme
code-pushed --no-sound "QUIET"    # skip the chime
code-pushed --dump "TEST"         # print one static frame (no animation)
code-pushed --png out.png "TEST"  # render a frame to an image
```

## Sound

A synthesized chord swell is generated on first run at
`~/.local/share/code-pushed/chime.wav`. Replace that file with any `.wav`
(e.g. the real "Victory Achieved" sound) to use your own.

## Project layout

```
code-pushed           # the whole program: rasterizer, renderer, animation, sound
shell/git-banner.sh   # git() wrapper + gitpush-test, sourced from ~/.bashrc
assets/Cinzel.ttf     # Trajan-style font (OFL licensed, from Google Fonts)
install.sh            # idempotent installer
```

## Uninstall

Delete the block between `# >>> code-pushed ... >>>` and `# <<< code-pushed <<<`
in `~/.bashrc`, then remove `~/.local/bin/code-pushed`,
`~/.local/share/code-pushed/`, and this directory.
