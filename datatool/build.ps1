<#
.SYNOPSIS
    Builds DataTool (overtools/OWLib) from source with the patches in .\patches applied.

.DESCRIPTION
    1. Clones (or updates) overtools/OWLib with submodules into -BuildDir and checks out -OwlibRef.
    2. Copies every file under patches\tactlib into the TACTLib submodule (skipping files upstream
       already has) and applies patches\datatool\*.patch with git apply.
    3. Finds a .NET SDK matching DataTool's TargetFramework, or installs one portably into -BuildDir.
    4. dotnet publish -> -BuildDir\out, writes out\patch-info.txt.
    5. With -InstallTo, backs up the existing folder (renamed with a timestamp) and copies the build there.

.EXAMPLE
    .\build.ps1 -InstallTo "E:\OW Mods\tools\datatool"
.EXAMPLE
    .\build.ps1 -Latest          # build upstream's current develop branch instead of the pinned commit
#>
param(
    [string]$BuildDir = "$env:LOCALAPPDATA\datatool-build",
    [string]$InstallTo = "",
    [string]$OwlibRef = "df522f0ceea8748dcb51463ceb990234ceb45c9a",   # overtools/OWLib develop, 2026-09-15 (v2.24.1.0+1149)
    [switch]$Latest
)

# "Continue", not "Stop": git and dotnet write progress to stderr, which PowerShell 5.1 would
# otherwise turn into a terminating NativeCommandError. Exit codes are checked explicitly instead.
$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$patches = Join-Path $here "patches"
$src = Join-Path $BuildDir "OWLib"
$out = Join-Path $BuildDir "out"
$upstream = "https://github.com/overtools/OWLib.git"

function Step($text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }
function Run($exe, [string[]]$arguments, $workDir) {
    $saved = Get-Location
    if ($workDir) { Set-Location $workDir }
    try {
        & $exe @arguments
        if ($LASTEXITCODE -ne 0) { throw "$exe $($arguments -join ' ') failed with exit code $LASTEXITCODE" }
    } finally { Set-Location $saved }
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git is not on PATH." }
New-Item -ItemType Directory -Force $BuildDir | Out-Null

Step "Source: overtools/OWLib"
if (-not (Test-Path (Join-Path $src ".git"))) {
    Run git @("clone", "--recurse-submodules", $upstream, $src)
}
Run git @("fetch", "--all", "--tags") $src
Run git @("reset", "--hard") $src
Run git @("clean", "-fd") $src
if ($Latest) { $OwlibRef = "origin/develop" }
Run git @("checkout", "--detach", $OwlibRef) $src
Run git @("submodule", "update", "--init", "--recursive", "--force") $src
Run git @("submodule", "foreach", "--recursive", "git reset --hard && git clean -fd") $src
$commit = (& git -C $src rev-parse --short HEAD).Trim()
$tactCommit = (& git -C (Join-Path $src "TACTLib") rev-parse --short HEAD).Trim()
Write-Host "OWLib $commit, TACTLib $tactCommit"

Step "Patches"
$applied = @()
$tactRoot = Join-Path $src "TACTLib"
Get-ChildItem (Join-Path $patches "tactlib") -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring((Join-Path $patches "tactlib").Length).TrimStart("\")
    $target = Join-Path $tactRoot $rel
    if (Test-Path $target) {
        Write-Host "skip   $rel (upstream already has it)" -ForegroundColor DarkGray
    } else {
        New-Item -ItemType Directory -Force (Split-Path -Parent $target) | Out-Null
        Copy-Item $_.FullName $target
        Write-Host "add    $rel"
        $applied += "tactlib/" + ($rel -replace "\\", "/")
    }
}
Get-ChildItem (Join-Path $patches "datatool") -Filter *.patch | Sort-Object Name | ForEach-Object {
    & git -C $src apply --reverse --check $_.FullName 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "skip   $($_.Name) (already in upstream)" -ForegroundColor DarkGray
        return
    }
    & git -C $src apply --check $_.FullName
    if ($LASTEXITCODE -ne 0) { throw "$($_.Name) does not apply to OWLib $commit. Fix or drop the patch and rerun." }
    Run git @("apply", $_.FullName) $src
    Write-Host "apply  $($_.Name)"
    $applied += "datatool/$($_.Name)"
}

Step ".NET SDK"
$csproj = Get-Content (Join-Path $src "DataTool\DataTool.csproj") -Raw
if ($csproj -notmatch "<TargetFramework>net(\d+)\.\d+</TargetFramework>") { throw "Cannot read TargetFramework from DataTool.csproj" }
$major = [int]$Matches[1]
$dotnet = $null
$cmd = Get-Command dotnet -ErrorAction SilentlyContinue
if ($cmd) {
    $sdks = & $cmd.Source --list-sdks
    if ($sdks | Where-Object { $_ -match "^$major\." }) { $dotnet = $cmd.Source }
}
if (-not $dotnet) {
    $portable = Join-Path $BuildDir "dotnet\dotnet.exe"
    if (Test-Path $portable) {
        $sdks = & $portable --list-sdks
        if ($sdks | Where-Object { $_ -match "^$major\." }) { $dotnet = $portable }
    }
}
if (-not $dotnet) {
    Write-Host "No .NET $major SDK found; installing a portable copy into $BuildDir\dotnet"
    $installer = Join-Path $BuildDir "dotnet-install.ps1"
    Invoke-WebRequest -Uri "https://dot.net/v1/dotnet-install.ps1" -OutFile $installer
    & $installer -Channel "$major.0" -InstallDir (Join-Path $BuildDir "dotnet")
    $dotnet = Join-Path $BuildDir "dotnet\dotnet.exe"
}
Write-Host "Using $dotnet"

Step "Build"
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "1"
$env:DOTNET_NOLOGO = "1"
Run $dotnet @("publish", "DataTool\DataTool.csproj", "-c", "Release", "-r", "win-x64", "--self-contained", "false", "-o", $out) $src
$info = @(
    "DataTool built $(Get-Date -Format 'yyyy-MM-dd HH:mm')",
    "overtools/OWLib $commit (TACTLib $tactCommit)",
    "Patches applied:"
) + ($applied | ForEach-Object { "  $_" })
Set-Content -Path (Join-Path $out "patch-info.txt") -Value $info -Encoding utf8
Write-Host "Output: $out"

if ($InstallTo) {
    Step "Install to $InstallTo"
    if (Test-Path $InstallTo) {
        $backup = "$InstallTo-backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        Rename-Item $InstallTo $backup
        Write-Host "Previous copy kept at $backup"
    }
    New-Item -ItemType Directory -Force $InstallTo | Out-Null
    Copy-Item (Join-Path $out "*") $InstallTo -Recurse
    Write-Host "Installed."
}

Write-Host ""
Write-Host "Smoke test:" -ForegroundColor Cyan
$exe = if ($InstallTo) { Join-Path $InstallTo "DataTool.exe" } else { Join-Path $out "DataTool.exe" }
Write-Host "  & `"$exe`" `"C:\Games\Overwatch`" list-heroes"
