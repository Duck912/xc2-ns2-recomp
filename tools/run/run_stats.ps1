# SPDX-License-Identifier: GPL-3.0-or-later
# One replay-cost run: the normal build started with [nvn] replay_stats on, killed after N seconds, its
# "replay" lines collected. Used to measure a change against the frame budget (HANDOVER 60.3/62.4).
#
#   pwsh -File tools\run\run_stats.ps1 -Tag base -Fps 60 -Seconds 70
#   pwsh -File tools\run\run_stats.ps1 -Tag push  -Fps 60 -Seconds 70 -Env @{ NXRT_NVN_PUSH_UNIFORMS = '0' }
#
# The replay_stats period is 600 logic frames (about 10 s at 60 fps): a 70 s run gives six lines, and the
# median of the last three is what a comparison should use (the first one still carries the load hitch).
param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [int]$Fps = 60,                                 # [xc2] fps; 0 = the game's own 30 Hz logic
    [int]$Hz = 60,                                  # present interval
    [int]$Seconds = 70,
    [string]$Press = 'A@16,A@22,A@30,LSU@46+8',     # the census scene: title -> new game -> standing in town
    [string]$Scale = '0.66',
    [int]$Stats = 600,                              # [nvn] replay_stats period (0 = off)
    [string]$Exe = 'xc2\build\boot\xc2_boot.exe',
    # Note: a hashtable cannot be passed through `pwsh -File`; set the NXRT_* variables in the caller instead -
    # the script only clears its own list, everything else is inherited.
    [hashtable]$Env = @{}
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)      # tools\run -> the repo root
$out = Join-Path $root 'work\replay_stats'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$log = Join-Path $out ('run-' + $Tag + '.log')
$exePath = if ([IO.Path]::IsPathRooted($Exe)) { $Exe } else { Join-Path $root $Exe }
if (-not (Test-Path $exePath)) { throw "no build at $exePath (run tools\build\build-boot.ps1 first)" }
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
$env:NXRT_NVN_REPLAY_STATS = "$Stats"
$env:XC2_PRESS = $Press
$env:NXRT_GFX_WINDOW_WIDTH = '1280'
$env:NXRT_GFX_WINDOW_HEIGHT = '720'
$env:NXRT_GFX_RENDER_SCALE = $Scale
foreach ($v in @('NXRT_NVN_FRAME_CSV', 'NXRT_NVN_SHOT_FRAMES', 'NXRT_NVN_SHOT_DIR', 'NXRT_NVN_PRESENT_MODE',
                 'NXRT_XC2_FPS_CENSUS', 'NXRT_NVN_TRACE_FRAME', 'NXRT_NVN_TRACE_SEC', 'NXRT_NVN_SKIP_FS_FILE')) {
    Remove-Item ("Env:" + $v) -ErrorAction SilentlyContinue
}
foreach ($k in $Env.Keys) { Set-Item -Path ("Env:" + $k) -Value ([string]$Env[$k]) }
Write-Host ("{0}: fps {1}, present {2} Hz, scale {3}, {4} s, stats {5}, press {6}" -f $Tag, $Fps, $Hz, $Scale, $Seconds, $Stats, $Press)

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

if (-not (Test-Path $log)) { throw "no log at $log" }
$lines = @(Get-Content $log)
$stats_ = @($lines | Where-Object { $_ -match 'rstats|replay .*ms/frame' })
Write-Host ("log: {0} lines, {1} replay stat lines" -f $lines.Count, $stats_.Count)
$frames = @($lines | Where-Object { $_ -match 'frame rate:' })
if ($frames.Count) {
    Write-Host 'frame rate (last 3):'
    $frames | Select-Object -Last 3 | ForEach-Object { '  ' + $_.Trim() }
}
if (-not $stats_.Count) { Write-Warning 'no replay stats in the log: [nvn] replay_stats never reached its period, or the run did not get into the game' }
else {
    Write-Host 'replay stats (last 4):'
    $stats_ | Select-Object -Last 4 | ForEach-Object { '  ' + $_.Trim() }
}
Write-Host ("log kept at {0}" -f $log)
