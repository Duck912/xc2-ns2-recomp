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

# A front end has to be able to say what is happening for half a minute, so every step writes a status file a GUI
# can poll and prints a PREFILL: line a console can show. The shape is deliberately trivial: key=value, one per line.
$status = Join-Path $Work 'prefill.status'
function Set-Status([string]$phase, [double]$elapsed, [int]$collected, [string]$note) {
    $body = @(
        ('phase=' + $phase),
        ('elapsed=' + [math]::Round($elapsed, 1)),
        ('budget=' + $Seconds),
        ('collected=' + $collected),
        ('note=' + $note)
    ) -join [Environment]::NewLine
    Set-Content -LiteralPath $status -Value $body -Encoding UTF8
}

$sw = [Diagnostics.Stopwatch]::StartNew()
Write-Output ('PREFILL: collecting shaders the cache lacks, up to ' + $Seconds + ' s (measured on a 12,104 cache: 24 s)')
Set-Status 'collect' 0 0 'starting the game headless'
$env:NXRT_NVN_DUMP_MISSING = $missing
$env:NXRT_NVN_DS_DEBUG = '1'
$log = Join-Path $Work 'prefill.log'
$p = Start-Process -FilePath $Exe -ArgumentList '--exefs', $Exefs, '--link', 'host', '--gfx', 'headless', '--log', $log -PassThru -WindowStyle Hidden
$deadline = (Get-Date).AddSeconds($Seconds)
$lastReport = 0
while ((Get-Date) -lt $deadline -and -not $p.HasExited) {
    Start-Sleep -Milliseconds 500
    $n = @(Get-ChildItem $missing -Filter 'code_*.bin' -ErrorAction SilentlyContinue).Count
    Set-Status 'collect' $sw.Elapsed.TotalSeconds $n 'running headless'
    if ($sw.Elapsed.TotalSeconds - $lastReport -ge 5) {
        $lastReport = $sw.Elapsed.TotalSeconds
        Write-Output ('PREFILL: ' + [math]::Round($sw.Elapsed.TotalSeconds) + '/' + $Seconds + ' s, ' + $n + ' block(s) so far')
    }
}
if (-not $p.HasExited) {
    # it is our own headless run, so closing it here is safe: the real launch comes next
    $p.Kill(); Start-Sleep -Seconds 2
    Write-Output ("prefill: stopped the collector after " + $Seconds + " s")
} else {
    Write-Output ('prefill: the collector exited on its own (' + $p.ExitCode + ')')
}

$blocks = @(Get-ChildItem $missing -Filter 'code_*.bin' -ErrorAction SilentlyContinue)
Write-Output ('PREFILL: collected ' + $blocks.Count + ' block(s) in ' + [math]::Round($sw.Elapsed.TotalSeconds, 1) + ' s')

# A collector that died early collected nothing, and writing the marker now would tell every later launch that the
# cache is complete when it is not. Say so and leave the marker unwritten, so the next launch tries again.
if ($p.HasExited -and $p.ExitCode -ne 0 -and $blocks.Count -eq 0) {
    Set-Status 'failed' $sw.Elapsed.TotalSeconds 0 ('the collector exited with ' + $p.ExitCode)
    Write-Output ('PREFILL: the collector exited with ' + $p.ExitCode + ' before finding anything; the cache is unchanged')
    Write-Output 'PREFILL: the next launch will try again - nothing is lost'
    exit 0
}
Set-Status 'translate' $sw.Elapsed.TotalSeconds $blocks.Count 'translating'
if ($blocks.Count -gt 0) {
    & (Join-Path $PSScriptRoot 'fill-cache.ps1') -Cache $Cache -Missing $missing -DsLog $log
}
New-Item -ItemType File -Force $marker | Out-Null
Set-Status 'done' $sw.Elapsed.TotalSeconds $blocks.Count 'the launch that follows is complete'
Write-Output ('PREFILL: done in ' + [math]::Round($sw.Elapsed.TotalSeconds, 1) + ' s, the launch that follows is complete')
