# darksouls-gitpush — Dark Souls banners for git.
# Sourced from ~/.bashrc or ~/.zshrc. Wraps `git` so:
#   push          ok: "CODE PUSHED" (gold)       fail: "YOU DIED" (red)
#   merge/rebase  ok: "VICTORY ACHIEVED" (gold)  fail: "YOU DIED" (red)
#   checkout -b / switch -c   area-name banner with the new branch (silver)
#   stash (push/save)         "HUMANITY RESTORED" (silver)
# The git exit code is preserved either way.

# resolved from PATH (pipx/pip entry point or the install.sh symlink)
CODE_PUSHED_BIN="${CODE_PUSHED_BIN:-code-pushed}"

# gold success banner with a souls counter (total commits on HEAD)
_code_pushed_victory() {
  local _souls
  _souls=$(command git rev-list --count HEAD 2>/dev/null)
  "$CODE_PUSHED_BIN" ${_souls:+--souls "$_souls"} "$1"
}

git() {
  local _rc
  case "$1" in
    push)
      command git "$@"; _rc=$?
      if [ $_rc -eq 0 ]; then
        _code_pushed_victory "CODE PUSHED"
      else
        "$CODE_PUSHED_BIN" --red "YOU DIED"
      fi
      return $_rc
      ;;
    merge|rebase)
      case " $* " in  # no banner for bookkeeping calls
        *" --abort "*|*" --quit "*|*" --edit-todo "*|*" --show-current-patch "*)
          command git "$@"; return $? ;;
      esac
      command git "$@"; _rc=$?
      if [ $_rc -eq 0 ]; then
        _code_pushed_victory "VICTORY ACHIEVED"
      else
        "$CODE_PUSHED_BIN" --red "YOU DIED"
      fi
      return $_rc
      ;;
    stash)
      case "${2:-push}" in
        push|save|-*)  # stash-creating forms (bare "git stash" included)
          local _before
          _before=$(command git rev-parse -q --verify refs/stash 2>/dev/null)
          command git "$@"; _rc=$?
          if [ $_rc -eq 0 ] && [ "$(command git rev-parse -q --verify \
                refs/stash 2>/dev/null)" != "$_before" ]; then
            "$CODE_PUSHED_BIN" --theme silver "HUMANITY RESTORED"
          fi
          return $_rc
          ;;
      esac
      command git "$@"
      return $?
      ;;
    checkout|switch)
      local _create="" _a
      for _a in "$@"; do
        [ "$_a" = "--" ] && break  # pathspecs follow; stop scanning
        case "$_a" in
          -b|-B|-c|-C|--create|--force-create) _create=1 ;;
        esac
      done
      command git "$@"; _rc=$?
      if [ $_rc -eq 0 ] && [ -n "$_create" ]; then
        local _br
        _br=$(command git branch --show-current 2>/dev/null)
        if [ -n "$_br" ]; then
          "$CODE_PUSHED_BIN" --theme silver \
            "$(printf '%s' "$_br" | tr '[:lower:]' '[:upper:]')"
        fi
      fi
      return $_rc
      ;;
  esac
  command git "$@"
}

# Preview the banners without touching git state.
#   gitpush-test          -> "CODE PUSHED" (gold, with souls counter)
#   gitpush-test fail     -> "YOU DIED" (red)
#   gitpush-test victory  -> "VICTORY ACHIEVED" (gold, with souls counter)
#   gitpush-test branch   -> "UNDEAD BURG" (silver area banner)
#   gitpush-test stash    -> "HUMANITY RESTORED" (silver)
gitpush-test() {
  case "${1:-}" in
    fail)    "$CODE_PUSHED_BIN" --red "YOU DIED" ;;
    victory) _code_pushed_victory "VICTORY ACHIEVED" ;;
    branch)  "$CODE_PUSHED_BIN" --theme silver "UNDEAD BURG" ;;
    stash)   "$CODE_PUSHED_BIN" --theme silver "HUMANITY RESTORED" ;;
    *)       _code_pushed_victory "CODE PUSHED" ;;
  esac
}
