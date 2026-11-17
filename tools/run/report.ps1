#Requires -Version 7.0
<#
.SYNOPSIS
  Run the game once with every diagnostic on and pack what it said into one zip.

.DESCRIPTION
  A bug report about rendering is worth nothing as prose: the four facts that decide a diagnosis are the validation
  layer's VUIDs, the capability lines the driver reports, whether the device was lost, and the frame times. This runs
  the game with all of them switched on and writes a folder plus a zip that can be attached to an issue as-is.

  It never stops the game. Close the window when you have seen enough (or let it crash); this packages whatever the
  run produced, including a crash.

.EXAMPLE
  pwsh -File tools/run/report.ps1                 # window, diagnostics on
  pwsh -File tools/run/report.ps1 -Headless       # no window, plus a frame-time CSV
#>
param(
    [switch]$Headless,
    # Package an existing log instead of running the game (re-packing a report someone sent, or checking this script).
    [string]$FromLog = '',
    [string]$Note = '',
    [int]$VuidLimit = 20,
    [switch]$NoZip
)
$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$outDir = Join-Path $root "work\reports\report-$stamp"
New-Item -ItemType Directory -Force $outDir | Out-Null

# --- run it ------------------------------------------------------------------------------------------
$logDir = Join-Path $root 'work\logs'
$before = @(Get-ChildItem $logDir -Filter 'play-301-*.log' -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$csv = Join-Path $outDir 'frame-times.csv'

$env:NXRT_GFX_VALIDATION   = '1'
$env:NXRT_NVN_DS_DEBUG     = '1'
$env:NXRT_NVN_FS_DEBUG     = '1'
$env:NXRT_NVN_FRAME_CSV    = $csv

if ($FromLog) {
    Write-Host "packaging $FromLog"
} else {
    $launcher = Join-Path $root 'tools\run\play-301.cmd'
    $launchArgs = @()
    if ($Headless) { $launchArgs += '-headless' }
    Write-Host "running: $launcher $($launchArgs -join ' ')"
    Write-Host 'close the game when you have seen enough; this packages the run afterwards.'
    & $launcher @launchArgs
}

# --- find the log the run wrote ----------------------------------------------------------------------
$after = @(Get-ChildItem $logDir -Filter 'play-301-*.log' -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$new = $after | Where-Object { $before -notcontains $_ }
if (-not $new) { $new = @($after | Sort-Object { (Get-Item $_).LastWriteTime } -Descending | Select-Object -First 1) }
$log = $new | Sort-Object { (Get-Item $_).LastWriteTime } -Descending | Select-Object -First 1
if ($FromLog) { $log = (Resolve-Path $FromLog).Path }
if (-not $log) { throw 'the run wrote no log at all' }
Copy-Item $log (Join-Path $outDir 'run.log') -Force
$lines = Get-Content $log

function Save-Section([string]$name, [string[]]$text) {
    $p = Join-Path $outDir $name
    if ($text -and $text.Count -gt 0) { Set-Content -LiteralPath $p -Value $text -Encoding UTF8 }
    else { Set-Content -LiteralPath $p -Value '(nothing in this run)' -Encoding UTF8 }
}

# 1. the validation layer, which is the whole point
$vuids = $lines | Where-Object { $_ -match 'VUID-|Undefined-Value-' }
$distinct = @()
$seen = @{}
foreach ($v in $vuids) {
    if ($v -match '(VUID-[A-Za-z0-9-]+|Undefined-Value-[A-Za-z]+)') {
        $id = $Matches[1]
        if (-not $seen.ContainsKey($id)) { $seen[$id] = 0 }
        $seen[$id]++
    }
}
$summary = @('count  id')
foreach ($k in ($seen.Keys | Sort-Object { -$seen[$_] })) { $summary += ('{0,-6} {1}' -f $seen[$k], $k) }
Save-Section 'vuids.txt' ($summary + @('') + @('--- first ' + $VuidLimit + ' full messages ---') + @($vuids | Select-Object -First $VuidLimit))

# 2. what the driver says it can do
Save-Section 'features.txt' @($lines | Where-Object { $_ -match 'gfx: features:|gfx: device ready:|gfx: swapchain' })

# 3. did the device go away
$lost = @($lines | Where-Object { $_ -match 'device lost|DEVICE_LOST|svcBreak|HOST EXCEPTION|vkQueueSubmit2 failed|vkWaitForFences' })
Save-Section 'device-lost.txt' $lost

# 4. what was running: the exe, the ini, the shader patches, the toolchain
$env_lines = @()
$exe = Join-Path $root 'xc2\build\boot-301\xc2_boot.exe'
if (Test-Path $exe) { $i = Get-Item $exe; $env_lines += ('exe        {0}  {1:N1} MB  {2}' -f $i.LastWriteTime, ($i.Length / 1MB), $i.FullName) }
$ini = Join-Path $root 'xc2\build\boot\nxrt.ini'
if (Test-Path $ini) {
    $env_lines += 'ini        ' + $ini
    foreach ($l in Get-Content $ini) { if ($l -match '^\s*[a-z_0-9]+\s*=') { $env_lines += '  ' + $l.Trim() } }
}
$patchDir = Join-Path $root 'xc2\game\shader-patch'
if (Test-Path $patchDir) {
    $env_lines += 'shader patches (not shippable, see docs):'
    foreach ($f in Get-ChildItem $patchDir -Filter '*.spv') {
        $env_lines += ('  {0}  {1} bytes  sha256 {2}' -f $f.Name, $f.Length, (Get-FileHash $f -Algorithm SHA256).Hash.Substring(0, 16))
    }
} else { $env_lines += 'shader patches: none installed (a clean build looks different from the maintainer one)' }
$cache = Join-Path $root 'xc2\build\boot\shader_cache\spirv'
if (Test-Path $cache) { $env_lines += ('shader cache  {0} modules' -f (Get-ChildItem $cache -Filter '*.spv').Count) }
$env_lines += 'toolchain:'
foreach ($c in 'clang-cl', 'cmake', 'ninja', 'dotnet') {
    $e = Get-Command $c -ErrorAction SilentlyContinue
    $env_lines += ('  {0,-10} {1}' -f $c, $(if ($e) { (& $e.Source --version 2>&1 | Select-Object -First 1) } else { 'not on PATH' }))
}
if ($Note) { $env_lines = @('note: ' + $Note, '') + $env_lines }
Save-Section 'environment.txt' $env_lines

# 5. frame times, when asked for a headless run
if (Test-Path $csv) {
    $n = (Get-Content $csv | Measure-Object -Line).Lines
    'frame-times.csv: ' + $n + ' rows' | Out-File (Join-Path $outDir 'frame-times.txt') -Encoding UTF8
} else {
    Set-Content -LiteralPath (Join-Path $outDir 'frame-times.txt') -Value '(no frame-time CSV: pass -Headless)' -Encoding UTF8
}

# 6. tell the reader what they are looking at
$readme = @(
    'Rendering report, ' + (Get-Date -Format 'yyyy-MM-dd HH:mm'),
    '',
    'run.log           the whole log of one run, validation layer on',
    'vuids.txt         every VUID by count, then the first ' + $VuidLimit + ' in full',
    'features.txt      the capability lines the driver reported',
    'device-lost.txt   anything that says the device went away (empty is good)',
    'environment.txt   the exe, the ini, the installed shader patches, the toolchain',
    'frame-times.csv   one line per presented frame (only with -Headless)',
    '',
    'Attach the zip to the issue as-is. Nothing here is game data: it is the log, the settings and the timing.'
)
Set-Content -LiteralPath (Join-Path $outDir 'README.txt') -Value $readme -Encoding UTF8

# --- zip ---------------------------------------------------------------------------------------------
$zip = Join-Path $root "work\reports\report-$stamp.zip"
if (-not $NoZip) {
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Compress-Archive -Path (Join-Path $outDir '*') -DestinationPath $zip -Force
}

Write-Host ''
Write-Host ('VUIDs        ' + $vuids.Count + ' lines, ' + $seen.Count + ' distinct')
Write-Host ('device lost  ' + $lost.Count + ' line(s)')
Write-Host ('folder       ' + $outDir)
if (-not $NoZip) { Write-Host ('zip          ' + $zip + '  (' + [math]::Round((Get-Item $zip).Length / 1KB, 0) + ' KB)') }
exit 0
