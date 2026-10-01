<#
.SYNOPSIS
    Extracts the data DataTool cannot filter per hero (abilities, perks, hero icons, intel database)
    for all heroes into <OutRoot>\_shared. Run copy-shared.py afterwards to pull one hero's slice out.
#>
param(
    [string]$OutRoot = "E:\OW_Extracts",
    [string]$DataTool = "E:\OW Mods\tools\datatool\DataTool.exe",
    [string]$Overwatch = "C:\Games\Overwatch"
)

$ErrorActionPreference = "Continue"
$out = Join-Path $OutRoot "_shared"
$logs = Join-Path $out "_logs"
New-Item -ItemType Directory -Force $logs | Out-Null
$status = Join-Path $logs "_status.txt"

function Run($name, [string[]]$arguments) {
    Add-Content $status "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] start $name"
    & $DataTool $Overwatch @arguments > (Join-Path $logs "$name.log")
    $code = $LASTEXITCODE
    Add-Content $status "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] end   $name rc=$code"
    if ($code -ne 0) { Write-Warning "$name exited with code $code" } else { Write-Host "$name done" }
}

Run "list-heroes" @("list-heroes")
Run "list-abilities" @("list-abilities")
Run "list-talents" @("list-talents")
Run "extract-hero-icons" @("extract-hero-icons", $out)
Run "extract-abilities" @("extract-abilities", $out)
Run "extract-talents" @("extract-talents", $out)
Run "extract-intel-database" @("extract-intel-database", $out)
Add-Content $status "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ALL DONE"
Write-Host "Finished. Output: $out"
