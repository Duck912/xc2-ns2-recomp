#Requires -Version 7.0
<#
.SYNOPSIS
  Say what this machine is missing to build the project, and nothing else.

.DESCRIPTION
  Checks the toolchain versions and every external source in deps.lock.json. Reports only; it never installs
  anything unless -Install is given, because a silent install turns "the build is not reproducible" into "the
  install failed halfway".

.EXAMPLE
  pwsh -File tools/bootstrap/doctor.ps1
  pwsh -File tools/bootstrap/doctor.ps1 -CacheDir D:\deps -Install
#>
param(
    # The archive cache CMake uses (gfx_deps.cmake: NXRT_DEPS_DIR), so a working machine reports "ok" rather than
    # "not in the cache" for sources that are already there.
    [string]$CacheDir = (Join-Path $env:LOCALAPPDATA 'nxrt\deps'),
    [switch]$Install,
    [switch]$Json
)
$ErrorActionPreference = 'Stop'
$lockPath = Join-Path $PSScriptRoot 'deps.lock.json'
if (-not (Test-Path $lockPath)) { throw "no deps.lock.json next to this script" }
$lock = Get-Content $lockPath -Raw | ConvertFrom-Json

$problems = @()
$report = @()
function Add-Row([string]$name, [string]$state, [string]$detail) {
    $script:report += [pscustomobject]@{ name = $name; state = $state; detail = $detail }
    if ($state -ne 'ok') { $script:problems += "$name : $detail" }
}

# --- the toolchain: versions, not hashes ---------------------------------------------------------------
$commands = @{ 'clang-cl' = 'clang-cl'; 'cmake' = 'cmake'; 'ninja' = 'ninja'; 'dotnet' = 'dotnet'; 'python' = 'python'; 'rustc' = 'rustc' }
foreach ($p in $lock.toolchain.PSObject.Properties) {
    $name = $p.Name
    if ($name -eq 'note') { continue }
    $want = $p.Value.version
    $cmd = $commands[$name]
    $exe = Get-Command $cmd -ErrorAction SilentlyContinue
    if (-not $exe) {
        Add-Row $name 'missing' "not on PATH (want $want)"
        continue
    }
    $out = & $exe.Source --version 2>&1 | Select-Object -First 1
    if ($out -match [regex]::Escape($want)) { Add-Row $name 'ok' $want }
    else { Add-Row $name 'version' "found '$out', lock says $want" }
}

# --- the sources ---------------------------------------------------------------------------------------
# The cache is keyed by the file name the URL ends with (CMake stores it that way), so look for that first and the
# lock's own name second.
function Get-Cached($src) {
    if (-not $CacheDir -or -not (Test-Path $CacheDir)) { return $null }
    $leaf = ($src.url -split '/')[-1]
    foreach ($n in @($leaf, $src.name)) {
        $p = Join-Path $CacheDir $n
        if ($n -and (Test-Path $p)) { return $p }
    }
    return $null
}

foreach ($s in $lock.sources) {
    if ($s.kind -eq 'git') {
        if (-not $s.commit) {
            Add-Row $s.name 'unpinned' "no commit recorded: a build today and a build next month can differ ($($s.url))"
            continue
        }
        $null = git ls-remote --heads $s.url 2>$null
        if ($LASTEXITCODE -eq 0) { Add-Row $s.name 'ok' "$($s.commit), reachable" }
        else { Add-Row $s.name 'unreachable' "$($s.url) does not answer; $($s.risk)" }
        continue
    }
    $cached = Get-Cached $s
    if ($cached) {
        # A zero-byte file in the cache is a download that failed and was left behind; the hash check would only say
        # "wrong hash", which reads like a supply-chain problem rather than a broken cache.
        if ((Get-Item $cached).Length -eq 0) {
            Add-Row $s.name 'empty' "$cached is 0 bytes: a failed download is sitting in the cache, delete it and rebuild"
            continue
        }
        if ($s.sha256) {
            $h = (Get-FileHash $cached -Algorithm SHA256).Hash.ToLower()
            if ($h -eq $s.sha256) { Add-Row $s.name 'ok' "cached, sha256 matches" }
            else { Add-Row $s.name 'hash' "$cached is $h, lock says $($s.sha256)" }
        } else { Add-Row $s.name 'ok' "cached (no hash in the lock)" }
        continue
    }
    if (-not $s.sha256) {
        Add-Row $s.name 'unpinned' "no sha256 in the lock ($($s.url))"
        continue
    }
    if ($Install -and $CacheDir) {
        New-Item -ItemType Directory -Force $CacheDir | Out-Null
        $ext = if ($s.url -match '\.(zip|tar\.gz|tgz)$') { $Matches[0] } else { '' }
        $dest = Join-Path $CacheDir ($s.name + $ext)
        Write-Host "  fetching $($s.name)"
        & curl.exe -sSL --fail --retry 3 --retry-delay 2 -o $dest $s.url
        if ($LASTEXITCODE -ne 0) { Add-Row $s.name 'fetch' "download failed: $($s.url)"; continue }
        $h = (Get-FileHash $dest -Algorithm SHA256).Hash.ToLower()
        if ($h -eq $s.sha256) { Add-Row $s.name 'ok' "fetched, sha256 matches" }
        else { Add-Row $s.name 'hash' "fetched $h, lock says $($s.sha256)" }
        continue
    }
    Add-Row $s.name 'missing' "not in the cache; fetch: curl -L -o <CacheDir>/$($s.name) $($s.url)"
}

# --- what a clean build cannot get from this repository ------------------------------------------------
foreach ($g in $lock.generated_artifacts) {
    $report += [pscustomobject]@{ name = $g.name; state = 'note'; detail = $g.action }
}

if ($Json) {
    $report | ConvertTo-Json -Depth 4
} else {
    foreach ($r in $report) {
        $mark = switch ($r.state) { 'ok' { '  ok  ' } 'note' { ' note ' } default { ' FAIL ' } }
        '{0} {1,-18} {2}' -f $mark, $r.name, $r.detail
    }
    ''
    if ($problems.Count -eq 0) { Write-Host 'nothing missing' }
    else {
        Write-Host ($problems.Count.ToString() + ' problem(s):')
        foreach ($p in $problems) { Write-Host ('  - ' + $p) }
    }
}
if ($problems.Count -gt 0) { exit 1 }
