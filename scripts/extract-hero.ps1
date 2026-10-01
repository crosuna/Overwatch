<#
.SYNOPSIS
    Extracts everything DataTool can scope to one hero into <OutRoot>\<Hero>.

.DESCRIPTION
    Runs, in order, with a log per step under <OutRoot>\<Hero>\_logs:
      list-unlocks (JSON and text), extract-hero-voice, extract-conversations,
      extract-unlocks "<Hero>|*=(leagueTeam=*)" --extract-refpose
    "(leagueTeam=*)" matters: DataTool's default is leagueTeam=none, so a plain "*=*" silently
    skips every esports team skin, spray and icon (OWL, World Cup, OWCS).
    Skins take about a minute each; an older hero with 140-160 skins (about half of them
    esports skins) runs for roughly 2 to 3 hours.

.EXAMPLE
    .\extract-hero.ps1 Genji
.EXAMPLE
    .\extract-hero.ps1 -Hero "Junker Queen" -OutRoot G:\OW_Extracts
#>
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Hero,
    [string]$OutRoot = "E:\OW_Extracts",
    [string]$DataTool = "E:\OW Mods\tools\datatool\DataTool.exe",
    [string]$Overwatch = "C:\Games\Overwatch",
    [switch]$SkipUnlocks,
    [switch]$SkipVoice
)

$ErrorActionPreference = "Continue"
$out = Join-Path $OutRoot $Hero
$logs = Join-Path $out "_logs"
New-Item -ItemType Directory -Force $logs | Out-Null
$status = Join-Path $logs "_status.txt"

function Run($name, [string[]]$arguments) {
    Add-Content $status "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] start $name"
    & $DataTool $Overwatch @arguments > (Join-Path $logs "$name.log")
    $code = $LASTEXITCODE
    Add-Content $status "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] end   $name rc=$code"
    if ($code -ne 0) { Write-Warning "$name exited with code $code (see $logs\$name.log)" } else { Write-Host "$name done" }
}

Write-Host "Extracting $Hero to $out"
Run "list-unlocks-json" @("list-unlocks", "--json", "--out=$logs\unlocks.json")
Run "list-unlocks-text" @("list-unlocks", $Hero)
if (-not $SkipVoice) {
    Run "extract-hero-voice" @("extract-hero-voice", $out, $Hero)
    Run "extract-conversations" @("extract-conversations", $out, $Hero)
}
if (-not $SkipUnlocks) {
    Run "extract-unlocks" @("extract-unlocks", $out, "$Hero|*=(leagueTeam=*)", "--extract-refpose")
}
Add-Content $status "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ALL DONE"
Write-Host "Finished. Logs: $logs"
