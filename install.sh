#!/usr/bin/env bash
# praise-the-git installer for Linux & macOS. Idempotent, safe to re-run.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
MARKER=">>> praise-the-git (Dark Souls git banner) >>>"
LEGACY_MARKER=">>> code-pushed (Dark Souls git banner) >>>"

# --- 1. install the `praise` command -------------------------------------
INSTALLED=""
if command -v pipx >/dev/null 2>&1; then
  if pipx install --force "$PROJECT_DIR" >/dev/null; then
    INSTALLED="pipx"
  fi
fi
if [ -z "$INSTALLED" ] && command -v python3 >/dev/null 2>&1; then
  if python3 -m pip install --user "$PROJECT_DIR" >/dev/null 2>&1; then
    INSTALLED="pip --user"
  fi
fi
if [ -z "$INSTALLED" ]; then
  # zero-dependency fallback: run straight from this checkout
  mkdir -p "$BIN_DIR"
  ln -sf "$PROJECT_DIR/praise" "$BIN_DIR/praise"
  INSTALLED="symlink -> $PROJECT_DIR"
fi
# clean up the pre-rename symlink, if that install path was used
[ -L "$BIN_DIR/code-pushed" ] && rm -f "$BIN_DIR/code-pushed"
echo "praise installed via: $INSTALLED"

# --- 2. shell integration (bash + zsh) ----------------------------------
add_block() {
  local rc="$1"
  # migrate: drop the block added under the project's old name
  if grep -qF "$LEGACY_MARKER" "$rc" 2>/dev/null; then
    sed -i.praise-bak "/$LEGACY_MARKER/,/<<< code-pushed <<</d" "$rc"
    echo "removed old code-pushed integration from $rc"
  fi
  if grep -qF "$MARKER" "$rc" 2>/dev/null; then
    echo "shell integration already present in $rc"
    return
  fi
  cat >> "$rc" << EOF

# $MARKER
[ -f "$PROJECT_DIR/shell/git-banner.sh" ] && . "$PROJECT_DIR/shell/git-banner.sh"
# <<< praise-the-git <<<
EOF
  echo "added shell integration to $rc"
}

FOUND_RC=""
for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
  if [ -f "$rc" ]; then
    add_block "$rc"
    FOUND_RC=yes
  fi
done
if [ -z "$FOUND_RC" ]; then
  # no rc file yet: create the default one for this platform's login shell
  case "$(uname -s)" in
    Darwin) add_block "$HOME/.zshrc" ;;
    *)      add_block "$HOME/.bashrc" ;;
  esac
fi

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "NOTE: if 'praise' is not found, add to PATH: export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

echo "done. Restart your shell (or 'source' your rc file), then run: praise-test"
