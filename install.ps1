# praise-the-git installer for Windows (PowerShell). Idempotent, safe to re-run.
#   irm https://raw.githubusercontent.com/mohammadrezanorouzii/praise-the-git/main/install.ps1 | iex
$ErrorActionPreference = "Stop"

$repo = "mohammadrezanorouzii/praise-the-git"
$appDir = if ($env:PRAISE_INSTALL_DIR) { $env:PRAISE_INSTALL_DIR }
          else { Join-Path $env:LOCALAPPDATA "praise-the-git\app" }

# --- 1. find Python 3 -----------------------------------------------------
if (Get-Command py -ErrorAction SilentlyContinue) { $python = "py" }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $python = "python" }
else {
    Write-Host "Python 3 not found. Install it from https://www.python.org/downloads/"
    Write-Host "(check 'Add python.exe to PATH' during setup), then re-run this script."
    exit 1
}

# --- 2. download the app --------------------------------------------------
Write-Host "downloading praise-the-git into $appDir ..."
$zip = Join-Path $env:TEMP "praise-the-git.zip"
$extract = Join-Path $env:TEMP "praise-the-git-extract"
Invoke-WebRequest "https://github.com/$repo/archive/refs/heads/main.zip" -OutFile $zip
if (Test-Path $extract) { Remove-Item $extract -Recurse -Force }
Expand-Archive $zip -DestinationPath $extract
if (Test-Path $appDir) { Remove-Item $appDir -Recurse -Force }
New-Item -ItemType Directory -Force (Split-Path $appDir) | Out-Null
Move-Item (Join-Path $extract "praise-the-git-main") $appDir
Remove-Item $zip
Remove-Item $extract -Recurse -Force

# --- 3. install the `praise` command --------------------------------------
& $python -m pip install --user --quiet $appDir
Write-Host "installed the 'praise' command"

# --- 4. install the `gitpush` shim -----------------------------------------
$scripts = & $python -c "import sysconfig; print(sysconfig.get_path('scripts', 'nt_user'))"
Copy-Item (Join-Path $appDir "shell\gitpush.cmd") (Join-Path $scripts "gitpush.cmd") -Force
Write-Host "installed gitpush.cmd to $scripts"

# --- 5. make sure the Scripts dir is on the user PATH ----------------------
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (($userPath -split ";") -notcontains $scripts) {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$scripts", "User")
    Write-Host "added $scripts to your user PATH"
}

Write-Host ""
Write-Host "Done. Open a NEW terminal, then:"
Write-Host "  praise               # preview the banner"
Write-Host "  gitpush origin main  # git push + banner"
