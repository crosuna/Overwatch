<#
.SYNOPSIS
    Looks through overtools/TACTLib and all of its public forks for manifest crypto procedures
    (ProCMF_<build>.cs / ProTRG_<build>.cs) newer than the ones this repo already carries.

.DESCRIPTION
    DataTool needs a new key/IV generator for every Overwatch build. Upstream usually publishes it
    within a week; sometimes a fork has it first. This script lists where the newest files are, with
    raw download URLs, so they can be dropped into patches\tactlib\TACTLib\Core\Product\Tank\{CMF,TRG}.
    Needs the GitHub CLI (gh) logged in.

.EXAMPLE
    .\find-new-procedures.ps1                 # report anything newer than the newest local patch
.EXAMPLE
    .\find-new-procedures.ps1 -Build 153619   # report anything newer than build 153619
#>
param(
    [int]$Build = 0,
    [int]$MaxForks = 60
)

$ErrorActionPreference = "Continue"   # gh prints 404s to stderr for branches without the folder; that is expected
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "GitHub CLI (gh) is not installed." }
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$cmfDir = "TACTLib/Core/Product/Tank/CMF"
$trgDir = "TACTLib/Core/Product/Tank/TRG"

if ($Build -eq 0) {
    $local = Get-ChildItem (Join-Path $here "patches\tactlib\$cmfDir") -Filter "ProCMF_*.cs" -ErrorAction SilentlyContinue |
        ForEach-Object { [int]($_.BaseName -replace "ProCMF_", "") } | Sort-Object -Descending | Select-Object -First 1
    if ($local) { $Build = $local }
}
Write-Host "Looking for procedures newer than build $Build"

function Get-Builds($repo, $ref, $dir) {
    $json = & gh api "repos/${repo}/contents/${dir}?ref=${ref}" 2>$null   # braces: "$dir?ref" would be read as one variable name
    if ($LASTEXITCODE -ne 0 -or -not $json) { return @() }
    ($json | ConvertFrom-Json) | ForEach-Object {
        if ($_.name -match "^Pro(CMF|TRG)_(\d+)\.cs$") { [pscustomobject]@{ Build = [int]$Matches[2]; Name = $_.name; Url = $_.download_url } }
    }
}

$repos = @("overtools/TACTLib")
$forks = & gh api --paginate "repos/overtools/TACTLib/forks?sort=newest&per_page=100" | ConvertFrom-Json
$forks | Sort-Object pushed_at -Descending | Select-Object -First $MaxForks | ForEach-Object { $repos += $_.full_name }

$found = @()
foreach ($repo in $repos) {
    $branches = & gh api --paginate "repos/$repo/branches?per_page=100" 2>$null | ConvertFrom-Json
    if (-not $branches) { continue }
    foreach ($b in $branches) {
        $files = @(Get-Builds $repo $b.name $cmfDir) + @(Get-Builds $repo $b.name $trgDir)
        $newer = $files | Where-Object { $_.Build -gt $Build }
        if ($newer) {
            $found += $newer | ForEach-Object { [pscustomobject]@{ Repo = $repo; Branch = $b.name; Build = $_.Build; File = $_.Name; Url = $_.Url } }
        }
    }
    Write-Host "." -NoNewline
}
Write-Host ""

if (-not $found) {
    Write-Host "Nothing newer than $Build found in upstream or $($repos.Count - 1) forks." -ForegroundColor Yellow
    exit 0
}
$found | Sort-Object Build, Repo, Branch, File -Descending | Format-Table Build, Repo, Branch, File, Url -AutoSize -Wrap | Out-Host
Write-Host ""
Write-Host "Download the CMF and TRG pair for the build you need into patches\tactlib\$cmfDir and ...\TRG, read them (they should be a short key/IV loop plus a 512-byte table and nothing else), then run build.ps1." -ForegroundColor Cyan
exit 0
