@echo off
setlocal enabledelayedexpansion
rem praise-the-git — use "gitpush" instead of "git push" in cmd.
rem Runs the real push, then shows CODE PUSHED / YOU DIED by exit code.
git push %*
set RC=%errorlevel%
if %RC% EQU 0 (
    set SOULS=
    for /f %%s in ('git rev-list --count HEAD 2^>nul') do set SOULS=%%s
    if defined SOULS (
        praise --souls !SOULS! "CODE PUSHED"
    ) else (
        praise "CODE PUSHED"
    )
) else (
    praise --red "YOU DIED"
)
exit /b %RC%
