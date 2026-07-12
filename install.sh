#!/usr/bin/env bash
# darksouls-gitpush installer — idempotent, safe to re-run.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
BASHRC="$HOME/.bashrc"
MARKER=">>> code-pushed (Dark Souls git banner) >>>"

mkdir -p "$BIN_DIR"
ln -sf "$PROJECT_DIR/code-pushed" "$BIN_DIR/code-pushed"
echo "linked $BIN_DIR/code-pushed -> $PROJECT_DIR/code-pushed"

if grep -qF "$MARKER" "$BASHRC" 2>/dev/null; then
  echo "shell integration already present in $BASHRC"
else
  cat >> "$BASHRC" << EOF

# $MARKER
[ -f "$PROJECT_DIR/shell/git-banner.sh" ] && . "$PROJECT_DIR/shell/git-banner.sh"
# <<< code-pushed <<<
EOF
  echo "added shell integration to $BASHRC"
fi

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "NOTE: $BIN_DIR is not in your PATH — add: export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

echo "done. Run 'source ~/.bashrc' then 'gitpush-test' to try it."
