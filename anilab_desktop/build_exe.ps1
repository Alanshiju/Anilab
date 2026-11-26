$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$AppName = "AniLab Desktop"
$DistDir = Join-Path $Root "dist"
$ScoopMpvDir = if ($env:MPV_DIR) { $env:MPV_DIR } else { Join-Path $env:USERPROFILE "scoop\apps\mpv\current" }

# Clean previous onedir folder if present so dist\ contains only the single .exe
$OldOnedir = Join-Path $DistDir $AppName
if (Test-Path $OldOnedir) {
    Remove-Item -Recurse -Force $OldOnedir
}

$PyInstallerArgs = @(
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--noconsole",
    "--name", $AppName,
    "--paths", "$Root\src",
    "--add-data", "$Root\scripts\resolver.py;scripts"
)

$IconPath = Join-Path $Root "assets\anilab.ico"
if (Test-Path $IconPath) {
    $PyInstallerArgs += @("--icon", $IconPath, "--add-data", "$IconPath;assets")
    Write-Host "[build_exe] Using custom icon $IconPath"
}

$MpvExe = Join-Path $ScoopMpvDir "mpv.exe"
if (Test-Path $MpvExe) {
    $PyInstallerArgs += @("--add-binary", "$MpvExe;player")
    Get-ChildItem -Path $ScoopMpvDir -Filter "*.dll" -ErrorAction SilentlyContinue | ForEach-Object {
        $PyInstallerArgs += @("--add-binary", "$($_.FullName);player")
    }
    Write-Host "[build_exe] Bundling mpv.exe into single EXE (player/)"
} else {
    Write-Warning "[build_exe] mpv.exe not found at $MpvExe; skipping player bundle."
}

$PyInstallerArgs += "$Root\src\anilab_desktop\__main__.py"

Write-Host "[build_exe] Building $AppName (--onefile --windowed --noconsole)..."
& pyinstaller @PyInstallerArgs

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

Write-Host "[build_exe] Build complete: $(Join-Path $DistDir "$AppName.exe")"
