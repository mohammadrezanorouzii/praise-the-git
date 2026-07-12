# darksouls-gitpush — Dark Souls banner on git push.
# Sourced from ~/.bashrc. Wraps `git` so a successful `git push` shows
# "CODE PUSHED" (gold) and a failed one shows "YOU DIED" (red).
# The push's exit code is preserved either way.

CODE_PUSHED_BIN="${CODE_PUSHED_BIN:-$HOME/.local/bin/code-pushed}"

git() {
  if [ "$1" = "push" ]; then
    command git "$@"
    local _rc=$?
    if [ $_rc -eq 0 ]; then
      "$CODE_PUSHED_BIN" "CODE PUSHED"
    else
      "$CODE_PUSHED_BIN" --red "YOU DIED"
    fi
    return $_rc
  fi
  command git "$@"
}

# Preview the banners without pushing anything (no git involved at all).
#   gitpush-test        -> "CODE PUSHED" (success banner)
#   gitpush-test fail   -> "YOU DIED" (failure banner)
gitpush-test() {
  if [ "$1" = "fail" ]; then
    "$CODE_PUSHED_BIN" --red "YOU DIED"
  else
    "$CODE_PUSHED_BIN" "CODE PUSHED"
  fi
}
