# SPDX-License-Identifier: GPL-3.0-or-later
# Launch XC2 hands-on: live keyboard / gamepad input, window, log file, F12 screenshots.
#
#   .\play.ps1                        # window + live input, 60 Hz presents (normal frame rate), log to play.log
#   .\play.ps1 -PresentHz 30          # the old 30 Hz pacing (comparison / recording)
#   .\play.ps1 -Press 'A@16,A@22'     # the same, plus scripted presses (they add to the live input)
#   .\play.ps1 -NoInput               # live input off (a whole run can then be scripted, XC2_NO_INPUT=1)
#
# Why -PresentHz 60 by default: XC2's logic steps 30 times a second, but it never asks the console for a present interval, so
# the host paces it ([nvn] present_interval_hz, HANDOVER 19). 60 shows every logic frame twice on a 60 Hz display: steady,
# no judder, and input stays responsive. 30 is the old behaviour (one present per logic step); 0 is uncapped, which is only
# for measuring throughput - at a rate the game cannot hold, the picture shows tearing / misplaced effects that look like
# rendering bugs (they are frame pacing, not rendering; HANDOVER 28.7).
#
# Controls (keyboard):
#   move      W A S D   or the arrow keys          camera        I J K L
#   A/confirm Space or Enter                       B/cancel      Backspace or Esc
#   X         U                                    Y             O
#   L / R     Q / E                                ZL / ZR       1 / 2
#   +         Tab or the + key                     -             the - key
#   stick clicks  Shift (L) / Ctrl (R)             screenshot    F12  -> shots_manual\shot_NNNN.png
# A gamepad is used when one is plugged in (bottom button = A, sticks and triggers as printed).
param(
    [string]$Press = '',
    [switch]$NoInput,
    [string]$Log = 'play.log',
    [string]$Gfx = 'window',
    [string]$Exefs = '',
    [int]$PresentHz = 60
)
$ErrorActionPreference = 'Stop'
$xc2 = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'xc2'
$bd = Join-Path $xc2 'build\boot'
# The four NSOs live in the project now (xc2\game\xc2ns2), copied from <fefw-recomp>\work\xc2ns2.
if (-not $Exefs) { $Exefs = Join-Path $xc2 'game\xc2ns2' }
if (-not (Test-Path $Exefs)) { throw "ExeFS not found: $Exefs (copy main, sdk, subsdk0, rtld, main.npdm into xc2\game\xc2ns2)" }
if (-not (Test-Path (Join-Path $bd 'xc2_boot.exe'))) { throw "xc2_boot.exe not built (run tools\build\build-boot.ps1 first)" }
# one instance at a time: the second one dies in the loader ("VirtualAlloc failed, error 487", HANDOVER 28.7)
$busy = Get-Process -Name xc2_boot -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $PID }
if ($busy) {
    Write-Host ("xc2_boot is already running (pid {0}): close that window first - only one instance can hold the guest's address space." -f ($busy.Id -join ', ')) -ForegroundColor Yellow
    exit 2
}
Push-Location $bd
try {
    # the automatic screenshot / trace knobs of earlier rounds would fight a hands-on session, and the diagnostic switches
    # (cull/stencil/depth overrides, shader skipping, missing-block dumps) change what the frame looks like
    'NXRT_NVN_SHOT_FRAMES','NXRT_NVN_TRACE_SEC','NXRT_NVN_TRACE_DUMP_TEX','NXRT_NVN_FRAME_CSV','NXRT_NVN_TRACE_FRAME',
    'NXRT_NVN_SKIP_FS_FILE','NXRT_NVN_DUMP_MISSING','NXRT_NVN_DEPTH_FUNC_EQUAL','NXRT_NVN_CULL_OFF_ALL','NXRT_NVN_STENCIL_OFF',
    'NXRT_NVN_DEPTH_OFF_FS','NXRT_NVN_CULL_OFF_FS','NXRT_NVN_DEPTH_WRITE_FS',
    'NXRT_NVN_SPV_HOT','NXRT_NVN_TRACE_UBO_DIR','NXRT_NVN_TRACE_UBO_BYTES','XC2_MODEL_PROBE' |
        ForEach-Object { Remove-Item "Env:$_" -ErrorAction SilentlyContinue }
    if ($PresentHz -gt 0) { $env:NXRT_NVN_PRESENT_INTERVAL_HZ = "$PresentHz" }
    else { $env:NXRT_NVN_PRESENT_INTERVAL_HZ = '0' }   # 0 = off; setting it keeps xc2_boot from putting its 30 back
    if ($Press) { $env:XC2_PRESS = $Press } else { Remove-Item Env:XC2_PRESS -ErrorAction SilentlyContinue }
    if ($NoInput) { $env:XC2_NO_INPUT = '1' } else { Remove-Item Env:XC2_NO_INPUT -ErrorAction SilentlyContinue }
    # keep the previous run's log: a crash trace must survive the next launch
    if (Test-Path (Join-Path $bd $Log)) { Copy-Item (Join-Path $bd $Log) (Join-Path $bd ([IO.Path]::GetFileNameWithoutExtension($Log) + '.prev.log')) -Force }
    Write-Host "window: Xenoblade Chronicles 2 (Switch 2 Edition)   presents: $(if ($PresentHz -gt 0) { "$PresentHz Hz" } else { 'uncapped' })   log: $bd\$Log"
    Write-Host "F12 saves shots_manual\shot_NNNN.png (plus .pfm / .hdrmap.png). Close the window or Ctrl+C to stop."
    & (Join-Path $bd 'xc2_boot.exe') --exefs $Exefs --link host --gfx $Gfx --log $Log
} finally {
    Pop-Location
}
