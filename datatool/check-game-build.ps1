<#
.SYNOPSIS
    Prints the installed Overwatch build and whether the local DataTool build supports it.
#>
param(
    [string]$Overwatch = "C:\Games\Overwatch",
    [string]$DataTool = "E:\OW Mods\tools\datatool\DataTool.exe"
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$info = Get-Content (Join-Path $Overwatch ".build.info")
$line = $info | Select-Object -Last 1
$fields = $line -split "\|"
$version = $fields | Where-Object { $_ -match "^\d+\.\d+\.\d+\.\d+\.\d+$" } | Select-Object -First 1
if (-not $version) { throw "Could not read the version from .build.info" }
$build = [int]($version -split "\.")[-1]
Write-Host "Installed Overwatch: $version (build $build)"

$have = Get-ChildItem (Join-Path $here "patches\tactlib\TACTLib\Core\Product\Tank\CMF") -Filter "ProCMF_*.cs" |
    ForEach-Object { [int]($_.BaseName -replace "ProCMF_", "") }
Write-Host "Procedures carried in this repo: $($have -join ', ')"

if (Test-Path $DataTool) {
    Write-Host "Asking DataTool..."
    $output = & $DataTool $Overwatch list-heroes | Select-String "Build version|procedure|Ready" | Select-Object -First 6
    $output | ForEach-Object { Write-Host "  $_" }
    if (-not $output) {
        Write-Host "DataTool printed nothing useful; run it by hand to see the error." -ForegroundColor Yellow
    } elseif ($output -match "is not supported") {
        Write-Host "DataTool does not support build $build yet. Run find-new-procedures.ps1." -ForegroundColor Yellow
    } elseif ($output -match "Ready") {
        Write-Host "DataTool works with this build." -ForegroundColor Green
    }
} else {
    Write-Host "DataTool not found at $DataTool (pass -DataTool)."
}
