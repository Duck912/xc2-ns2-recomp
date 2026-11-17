# Run the game headless once, collect the shaders the cache lacks, translate them, then let the real launch begin.
# Without this the FIRST launch renders with gaps - a black title screen on a fresh cache - and only the second one is
# complete. The prefill costs about half a minute and happens once per cache.
param(
    [Parameter(Mandatory = $true)][string]$Exe,
    [Parameter(Mandatory = $true)][string]$Exefs,
    [Parameter(Mandatory = $true)][string]$Cache,
    [Parameter(Mandatory = $true)][string]$Work,
    [int]$Seconds = 25,
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
$marker = Join-Path $Work '.prefilled'
if ((Test-Path $marker) -and -not $Force) { exit 0 }

$missing = Join-Path $Work 'missing-301'
if (Test-Path $missing) { Remove-Item $missing -Recurse -Force }
New-Item -ItemType Directory -Force $missing | Out-Null

Write-Output 'prefill: starting the game headless to collect the shaders the cache lacks'
$env:NXRT_NVN_DUMP_MISSING = $missing
$env:NXRT_NVN_DS_DEBUG = '1'
$log = Join-Path $Work 'prefill.log'
$p = Start-Process -FilePath $Exe -ArgumentList '--exefs', $Exefs, '--link', 'host', '--gfx', 'headless', '--log', $log -PassThru -WindowStyle Hidden
$deadline = (Get-Date).AddSeconds($Seconds)
while ((Get-Date) -lt $deadline -and -not $p.HasExited) { Start-Sleep -Milliseconds 500 }
if (-not $p.HasExited) {
    # it is our own headless run, so closing it here is safe: the real launch comes next
    $p.Kill(); Start-Sleep -Seconds 2
    Write-Output ("prefill: stopped the collector after " + $Seconds + " s")
} else {
    Write-Output ('prefill: the collector exited on its own (' + $p.ExitCode + ')')
}

$blocks = @(Get-ChildItem $missing -Filter 'code_*.bin' -ErrorAction SilentlyContinue)
Write-Output ('prefill: collected ' + $blocks.Count + ' block(s)')
if ($blocks.Count -gt 0) {
    & (Join-Path $PSScriptRoot 'fill-cache.ps1') -Cache $Cache -Missing $missing -DsLog $log
}
New-Item -ItemType File -Force $marker | Out-Null
Write-Output 'prefill: done, the launch that follows is complete'
