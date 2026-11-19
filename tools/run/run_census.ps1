# SPDX-License-Identifier: GPL-3.0-or-later
# One census run: the census build (build-census.ps1) started with the recorder on, killed after N seconds. The census
# file is rewritten every 600 logic frames while it runs, so a forced kill keeps the last table.
#
#   pwsh -File tools\run\run_census.ps1 -Tag census-30 -Fps 0  -Seconds 90    # native 30 Hz logic
#   pwsh -File tools\run\run_census.ps1 -Tag census-60 -Fps 60 -Seconds 90    # [xc2] fps = 60
#
# Both runs present at 60 Hz, the same scripted input, the same save. fps_follow is off in both so the step is exactly
# 1 / fps and a site's mean delta classifies cleanly (a hitch only makes the game slower, not the census wrong).
param(
    [Parameter(Mandatory = $true)][string]$Tag,     # census-30 / census-60
    [int]$Fps = 0,                                  # 0 = the game's own 30 Hz logic; 60 = 60 fps mode
    [int]$Hz = 60,                                  # present interval, 60 in both runs
    [int]$Seconds = 90,
    [string]$Press = 'A@16,A@22,A@30,LSU@46+8',
    [string]$Scale = '0.66',
    [string]$Exe = 'xc2\build\boot-census\xc2_boot.exe',
    [string]$Tick = ''            # main-relative offset of the frame clock (default: the build's own); must be an entryhook site
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)      # tools\run -> the repo root
$out = Join-Path $root 'work\fps_census'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$census = Join-Path $out ($Tag + '.txt')
$log = Join-Path $out ('run-' + $Tag + '.log')
$exePath = if ([IO.Path]::IsPathRooted($Exe)) { $Exe } else { Join-Path $root $Exe }
if (-not (Test-Path $exePath)) { throw "no census build at $exePath (run tools\build\build-census.ps1 first)" }
$bd = Split-Path -Parent $exePath

# one xc2_boot at a time, and 10 s after a kill before the next (VirtualAlloc fails with 487 otherwise)
Get-Process -Name xc2_boot -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "stopping the running xc2_boot (pid $($_.Id))"
    Stop-Process -Id $_.Id -Force
}
Start-Sleep -Seconds 10

$env:NXRT_NVN_PRESENT_INTERVAL_HZ = "$Hz"
if ($Fps -gt 0) { $env:NXRT_XC2_FPS = "$Fps" } else { Remove-Item Env:NXRT_XC2_FPS -ErrorAction SilentlyContinue }
$env:NXRT_XC2_FPS_FOLLOW = '0'
$env:NXRT_XC2_FPS_CENSUS = $census
$env:NXRT_XC2_FPS_CENSUS_EVERY = '600'
$env:XC2_PRESS = $Press
$env:NXRT_GFX_WINDOW_WIDTH = '1280'
$env:NXRT_GFX_WINDOW_HEIGHT = '720'
$env:NXRT_GFX_RENDER_SCALE = $Scale
foreach ($v in @('NXRT_NVN_FRAME_CSV', 'NXRT_NVN_SHOT_FRAMES', 'NXRT_NVN_SHOT_DIR', 'NXRT_XC2_FPS_CENSUS_TICK', 'NXRT_NVN_PRESENT_MODE')) {
    Remove-Item ("Env:" + $v) -ErrorAction SilentlyContinue
}
# a clock other than the build's default (the address must be in build\sites-main-census.txt, i.e. lifted with an entryhook)
if ($Tick) { $env:NXRT_XC2_FPS_CENSUS_TICK = $Tick }
Write-Host ("{0}: fps {1}, present {2} Hz, render scale {3}, {4} s, press {5}" -f $Tag, $Fps, $Hz, $Scale, $Seconds, $Press)

Remove-Item $census -ErrorAction SilentlyContinue
Remove-Item $log -ErrorAction SilentlyContinue
Push-Location $bd
try {
    $argv = @('--exefs', '..\..\game\xc2ns2', '--link', 'host', '--gfx', 'window', '--log', ('"' + $log + '"'))
    $p = Start-Process -FilePath $exePath -ArgumentList $argv -PassThru
    Write-Host ("launched pid {0}, sampling {1} s" -f $p.Id, $Seconds)
    Start-Sleep -Seconds $Seconds
    if ($p.HasExited) { Write-Host "process exited early (code $($p.ExitCode))" } else { Stop-Process -Id $p.Id -Force }
} finally { Pop-Location }
Start-Sleep -Seconds 10

# ---- the checks of docs (the census section): 30 +- 2 or 60 +- 4 updates a second ---------------------------------------
if (-not (Test-Path $log)) { throw "no log at $log" }
$lines = @(Get-Content $log | Where-Object { $_ -match 'fps census:' })
$writes = @($lines | Where-Object { $_ -match 'records ->' })
Write-Host ("log: {0} 'fps census:' lines, {1} file writes" -f $lines.Count, $writes.Count)
if (-not $writes.Count) {
    throw 'the log has no census write: the clock hook never fired (build\sites-main-census.txt needs the clock address as an "entryhook") or the probes never ran'
}
$last = $writes[-1]
if ($last -notmatch 'fps census: (\d+) updates \(([\d.]+)/s\)') { throw "cannot read the last census line: $last" }
$updates = [int]$Matches[1]
$rate = [double]$Matches[2]
$lo = if ($Fps -ge 60) { 56 } else { 28 }
$hi = if ($Fps -ge 60) { 64 } else { 32 }
Write-Host ("clock: {0} updates in {1} s ({2:N1}/s reported, {3:N1}/s of the wall clock)" -f $updates, $Seconds, $rate, ($updates / $Seconds))
if ($rate -lt $lo -or $rate -gt $hi) {
    Write-Warning ("the update rate {0:N1}/s is outside {1}..{2}: fix the clock before trusting the numbers (the limiter at main+0x722a04 is the alternative tick)" -f $rate, $lo, $hi)
} else {
    Write-Host ("ok: {0:N1} updates/s (expected {1}..{2})" -f $rate, $lo, $hi)
}
# 600 updates between two writes: 20 s at 30 Hz, 10 s at 60 fps
$wantWrites = if ($Fps -ge 60) { 8 } else { 4 }
if ($writes.Count -lt $wantWrites) { Write-Warning ("only {0} writes, expected at least {1} (600 updates each)" -f $writes.Count, $wantWrites) }

if (-not (Test-Path $census)) { throw "no census file at $census" }
$rows = @(Get-Content $census | Where-Object { $_ -notmatch '^updates ' }).Count
Write-Host ("census: {0}, {1} site lines" -f $census, $rows)
if ($rows -lt 1000) { Write-Warning ("only {0} site lines: the probes are probably not in this build" -f $rows) }
Write-Host 'next:  python tools\analysis\fps_census.py --at30 work\fps_census\census-30.txt --at60 work\fps_census\census-60.txt --sites xc2\build\fps_sites.txt --out work\fps_census\report.txt --csv work\fps_census\report.csv'
