# SPDX-License-Identifier: GPL-3.0-or-later
# The frame-counter census build: main lifted with a fps_census probe before every counter site (nxrecomp/fps.py), in
# directories of its own so the normal build (build\lift, build\obj, build\lib, build\boot) is never touched.
#
#   .\scripts\build-census.ps1              # scan (if needed), lift, compile, link -> build\boot-census\xc2_boot.exe
#   .\scripts\build-census.ps1 -Rescan      # re-run the site scanner first
#   .\scripts\build-census.ps1 -SkipLift    # reuse build\lift-census\main (only the compile and the link run)
#
# Products: build\fps_sites.txt (the sites), build\sites-main-census.txt (build\sites-main.txt verbatim + the clock's
# entry hook), build\lift-census\main, build\obj-census\main, build\lib-census\main.lib,
# build\boot-census\xc2_boot.exe. Roll back by deleting those four directories.
param(
    [switch]$Rescan,
    [switch]$SkipLift,
    [int]$Jobs = 10
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$nx = (Resolve-Path (Join-Path $root '..\third_party\nxrecomp\recomp')).Path
$build = Join-Path $root 'build'
$py = if ($env:XC2_PYTHON) { $env:XC2_PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { (Get-Command python).Source } else { throw 'no python: set $env:XC2_PYTHON' }
$env:PYTHONPATH = $nx
$envScript = $env:XC2_ENV   # optional: a script that puts clang-cl / llvm-lib / dotnet on PATH
if (Test-Path $envScript) { . $envScript | Out-Null }

$sites = Join-Path $build 'fps_sites.txt'
$censusSites = Join-Path $build 'sites-main-census.txt'
$liftDir = Join-Path $build 'lift-census\main'
$objDir = Join-Path $build 'obj-census\main'
$libDir = Join-Path $build 'lib-census'
$lib = Join-Path $libDir 'main.lib'
$bootDir = Join-Path $build 'boot-census'
$mainNso = Join-Path $root 'game\xc2ns2\main'

# ---- 1. the sites --------------------------------------------------------------------------------------
if ($Rescan -or -not (Test-Path $sites)) {
    Write-Host 'scan: main -> build\fps_sites.txt'
    $t = [Diagnostics.Stopwatch]::StartNew()
    & $py -m nxrecomp.fps $mainNso --base 0x7100000000 --out $sites
    if ($LASTEXITCODE -ne 0) { throw 'the site scan failed' }
    Write-Host ("scan: {0:N1}s" -f $t.Elapsed.TotalSeconds)
} else {
    $n = @(Get-Content $sites | Where-Object { $_ -notmatch '^\s*#' }).Count
    Write-Host "scan: build\fps_sites.txt has $n sites (-Rescan redoes it)"
}

# ---- 2. the census site list: build\sites-main.txt verbatim + the clock's entry hook ---------------------
# Without the clock's "entryhook" the hook never fires and every update count stays 0 (HANDOVER 58: 0x73a8f4 taught us
# that; 0x713754 - the step getter - is not called per frame, so the clock is the game's own limiter 0x722a04).
# ASCII only: the lifter reads these files with the system locale (GBK here).
$clock = '7100722a04'
$lines = @(Get-Content (Join-Path $build 'sites-main.txt'))
if (-not ($lines | Where-Object { $_ -match "^entryhook\s+$clock\b" })) {
    $lines += "entryhook $clock   # ml::DevGraphNx::renderSyncSys: the game's own frame limiter, one entry per logic frame"
}
Set-Content -LiteralPath $censusSites -Value $lines -Encoding ascii
Write-Host "sites: build\sites-main-census.txt, $($lines.Count) lines"

# ---- 3. lift main with the probes ------------------------------------------------------------------------
if ($SkipLift) {
    if (-not (Test-Path $liftDir)) { throw "-SkipLift but $liftDir does not exist" }
    Write-Host 'lift: skipped (-SkipLift)'
} else {
    Write-Host 'lift: main -> build\lift-census\main'
    $t = [Diagnostics.Stopwatch]::StartNew()
    Push-Location $nx
    try {
        $liftArgs = @('-m', 'nxrecomp', 'lift', $mainNso, $liftDir, '--game', 'xc2ns2', '--name', 'main',
                      '--base', '0x7100000000', '--jobs', "$Jobs", '--sites', $censusSites, '--census-sites', $sites)
        # scripts\fps_counters.txt (the frame counters converted to the game's time, HANDOVER 59) is optional: without it
        # every site keeps the game's own value, i.e. this build is the plain census build.
        $counters = Join-Path $PSScriptRoot 'fps_counters.txt'
        if (Test-Path $counters) { $liftArgs += @('--fps-counters', $counters) }
        else { Write-Host 'counters: scripts\fps_counters.txt not found: no counter is converted' }
        & $py @liftArgs 2>&1 | ForEach-Object { Write-Host "  $_" }
        if ($LASTEXITCODE -ne 0) { throw 'lift failed for main' }
    } finally { Pop-Location }
    Write-Host ("lift: {0:N1}s" -f $t.Elapsed.TotalSeconds)
}

# ---- 4. compile every shard ------------------------------------------------------------------------------
$inc = Join-Path $nx 'include'
New-Item -ItemType Directory -Force -Path $objDir | Out-Null
$ccJobs = @()
foreach ($s in (Get-ChildItem $liftDir -Filter '*.cpp')) {
    $ccJobs += [pscustomobject]@{ Src = $s.FullName; Obj = (Join-Path $objDir ($s.BaseName + '.obj')); Inc = $inc; Dir = $liftDir }
}
Write-Host ("compile: {0} translation unit(s) to build" -f $ccJobs.Count)
$t = [Diagnostics.Stopwatch]::StartNew()
$res = $ccJobs | ForEach-Object -ThrottleLimit $Jobs -Parallel {
    $o = & clang-cl.exe /nologo /std:c++20 /O2 /c "/I$($_.Inc)" "/I$($_.Dir)" $_.Src "/Fo$($_.Obj)" 2>&1 | Out-String
    [pscustomobject]@{ Src = $_.Src; Exit = $LASTEXITCODE; Errors = ([regex]::Matches($o, 'error:')).Count; Log = $o }
}
$bad = @($res | Where-Object { $_.Exit -ne 0 })
Write-Host ("compile: {0} ok, {1} failed, {2:N1}s" -f ($res.Count - $bad.Count), $bad.Count, $t.Elapsed.TotalSeconds)
if ($bad.Count) {
    foreach ($b in $bad) { Write-Host ($b.Log -split '\r?\n' | Where-Object { $_ -match 'error:' } | Select-Object -First 5) }
    throw 'compile failed'
}

# ---- 5. one static library ---------------------------------------------------------------------------------
New-Item -ItemType Directory -Force -Path $libDir | Out-Null
$objs = Get-ChildItem $objDir -Filter '*.obj' | ForEach-Object { '"' + $_.FullName + '"' }
$rsp = Join-Path $build 'obj-census\main.rsp'
Set-Content -LiteralPath $rsp -Value $objs -Encoding ascii
& llvm-lib.exe /nologo "/OUT:$lib" "@$rsp"
if ($LASTEXITCODE -ne 0) { throw 'llvm-lib failed for main' }
Write-Host ("lib: {0} ({1:N1} MB)" -f $lib, ((Get-Item $lib).Length / 1MB))

# ---- 6. xc2_boot.exe ---------------------------------------------------------------------------------------
& (Join-Path $PSScriptRoot 'build-boot.ps1') -MainLib $lib -OutDir $bootDir

# ---- 7. the files the runtime wants next to the exe ---------------------------------------------------------
# [nvn] pipeline_cache and pipeline_keys are relative paths, so the census build needs copies of its own: without them
# every shader is compiled again (and the normal build's cache must not be rewritten).
# The RomFS is a relative path too ("game/romfs"): a junction to the normal build's copy (10 GB, read only).
$gameLink = Join-Path $bootDir 'game'
if (-not (Test-Path $gameLink)) {
    $src = Join-Path $build 'boot\game'
    if (Test-Path $src) { New-Item -ItemType Junction -Path $gameLink -Target $src | Out-Null; Write-Host "junction: game -> $src" }
}
foreach ($f in @('nxrt.ini', 'controls.ini', 'pipeline_cache.bin', 'pipeline_keys.bin')) {
    $dst = Join-Path $bootDir $f
    if (-not (Test-Path $dst)) {
        $src = Join-Path $build ('boot\' + $f)
        if (Test-Path $src) {
            Copy-Item $src $dst
            Write-Host ("copied: {0} ({1:N1} MB)" -f $f, ((Get-Item $dst).Length / 1MB))
        }
    }
}

Write-Host ''
Write-Host "census build: $(Join-Path $bootDir 'xc2_boot.exe')"
Write-Host 'run it:  pwsh -File xc2\scripts\run_census.ps1 -Tag census-30 -Fps 0 -Seconds 90'
