@echo off
rem praise-the-git installer for Windows (cmd). Safe to re-run.
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel% EQU 0 (set "PY=py") else (set "PY=python")

echo Installing package (praise command + Pillow)...
%PY% -m pip install --user .
if errorlevel 1 (
    echo pip install failed. Is Python 3 installed? https://www.python.org/downloads/
    exit /b 1
)

rem Find the per-user Scripts directory pip installed praise.exe into
for /f "delims=" %%i in ('%PY% -c "import sysconfig; print(sysconfig.get_path('scripts', 'nt_user'))"') do set "SCRIPTS=%%i"

copy /y "shell\gitpush.cmd" "%SCRIPTS%\gitpush.cmd" >nul
echo Installed gitpush.cmd to %SCRIPTS%

rem Make sure that directory is on the user PATH
echo ;%PATH%; | find /i ";%SCRIPTS%;" >nul
if errorlevel 1 (
    echo.
    echo NOTE: %SCRIPTS% is not on your PATH.
    echo Add it via: System Properties ^> Environment Variables, or run:
    echo     setx PATH "%%PATH%%;%SCRIPTS%"
    echo then open a new terminal.
)

echo.
echo Done. In cmd use:  gitpush        (instead of "git push")
echo Preview banners:   praise         /  praise --red "YOU DIED"
endlocal
