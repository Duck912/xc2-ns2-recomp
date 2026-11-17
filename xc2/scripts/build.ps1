# SPDX-License-Identifier: GPL-3.0-or-later
# xc2ns2 scaffold build: lift the four modules with nxrecomp, compile every shard with clang-cl, link xc2ns2_stub.exe.
#
#   . .\scripts\build.ps1                 # everything (lift if stale, compile, link, run the smoke test)
#   . .\scripts\build.ps1 -Run:$false     # build only
#   . .\scripts\build.ps1 -SkipLift       # reuse build\lift (the C++ is current)
#   . .\scripts\build.ps1 -Clean          # drop build\obj and build\bin first
#
# Inputs: the ExeFS modules (default <repo>\game\xc2ns2, override with -Exefs or $env:XC2_EXEFS).
# Hook sites: build\sites-<module>.txt if present, else the shipped xc2\sites\sites-<module>.txt.
# Toolchain: clang-cl and llvm-lib on PATH (Visual Studio Build Tools + LLVM), or point $env:XC2_ENV at a script
# that sets them up. Python: $env:XC2_PYTHON, else `python` on PATH.
param(
    [string]$Exefs = $(if ($env:XC2_EXEFS) { $env:XC2_EXEFS } else { Join-Path (Split-Path -Parent $PSScriptRoot) 'game\xc2ns2' }),
    [string[]]$Modules = @('main', 'sdk', 'subsdk0', 'rtld'),   # accepts -Modules main,sdk and -Modules 'main,sdk'
    [switch]$SkipLift,
    [switch]$Clean,
    [switch]$Run = $true,
    [int]$Jobs = 10,
    # Where the lift, the objects and the per-module libraries go. The defaults are the four-module development
    # route; the retail 3.0.1 route keeps its own (build\lift-301, build\lib-301) so the two never overwrite
    # each other. Relative paths resolve against the directory you run the script from.
    [string]$LiftDir = '',
    [string]$ObjDir = '',
    [string]$LibDir = ''
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$nx = (Resolve-Path (Join-Path $root '..\third_party\nxrecomp\recomp')).Path
$build = Join-Path $root 'build'
function Resolve-OutDir([string]$value, [string]$fallback) {
    $p = if ($value) { $value } else { $fallback }
    if (-not [System.IO.Path]::IsPathRooted($p)) { $p = Join-Path (Get-Location).Path $p }
    return $p
}
$liftDir = Resolve-OutDir $LiftDir (Join-Path $build 'lift')
$objDir  = Resolve-OutDir $ObjDir  (Join-Path $build 'obj')
$libDir  = Resolve-OutDir $LibDir  (Join-Path $build 'lib')

# Optional: a script that puts clang-cl/llvm-lib/python/dotnet on PATH. It is loaded first, because it may be what
# puts python there; a machine that already has the tools needs nothing here.
if ($env:XC2_ENV) {
    if (-not (Test-Path $env:XC2_ENV)) { throw "XC2_ENV points at a file that does not exist: $env:XC2_ENV" }
    . $env:XC2_ENV | Out-Null
}
$py = if ($env:XC2_PYTHON) { $env:XC2_PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { (Get-Command python).Source } else { throw 'no python: set $env:XC2_PYTHON or put python on PATH' }

# The lift runs with the nxrecomp directory as the working directory, so a relative -Exefs has to be resolved here,
# against the directory the caller used.
if (-not [System.IO.Path]::IsPathRooted($Exefs)) { $Exefs = Join-Path (Get-Location).Path $Exefs }

if ($Clean) { Remove-Item -Recurse -Force (Join-Path $build 'obj'), (Join-Path $build 'bin') -ErrorAction SilentlyContinue }

$mods = $Modules | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ }
# Guest load addresses. main is the console's fixed 0x7100000000; the other modules are placed by the runtime in the
# SDK region (nxrt/memory.h: kSdkBase..kHeapBase) and the FEFW fork puts them at these addresses (recomp/games/fefw).
$bases = @{ 'main' = '0x7100000000'; 'sdk' = '0x7500000000'; 'subsdk0' = '0x7600000000'; 'subsdk1' = '0x7640000000'; 'subsdk2' = '0x7680000000'; 'subsdk3' = '0x76C0000000'; 'rtld' = '0x7700000000' }
$env:PYTHONPATH = $nx
$sw = [Diagnostics.Stopwatch]::StartNew()

# ---- 1. lift ------------------------------------------------------------------------------------------
if (-not $SkipLift) {
    Push-Location $nx
    try {
        foreach ($m in $mods) {
            $src = Join-Path $Exefs $m
            if (-not (Test-Path $src)) { throw "missing module: $src" }
            if (-not $bases.ContainsKey($m)) { throw "no guest base for module $m (add it to `$bases)" }
            $base = $bases[$m]
            $out = Join-Path $liftDir $m
            $stampFile = Join-Path $out '.base'
            $fresh = (Test-Path $out) -and (Get-ChildItem $out -Filter 'module_*.cpp' -ErrorAction SilentlyContinue) -and
                     ((Get-Item (Get-ChildItem $out -Filter 'module_*.cpp' | Select-Object -First 1).FullName).LastWriteTime -gt (Get-Item $src).LastWriteTime) -and
                     ((Test-Path $stampFile) -and ((Get-Content $stampFile -Raw).Trim() -eq $base))
            if ($fresh) { Write-Host "lift $m : up to date (base $base)"; continue }
            $t = [Diagnostics.Stopwatch]::StartNew()
            # Site list (entry/mid hooks compiled into the lifted code). build\sites-<module>.txt wins if it exists, so a
            # local experiment can add hooks without touching the repository; otherwise the shipped xc2\sites\ copy is
            # used. Without --sites the lifter emits no nx_hook_entry, and every hook_add_entry in xc2_boot.cpp silently
            # does nothing.
            $sitesArg = @()
            foreach ($cand in @((Join-Path $build "sites-$m.txt"), (Join-Path $root "sites\sites-$m.txt"))) {
                if (Test-Path $cand) { $sitesArg = @('--sites', $cand); break }
            }
            # Frame counters converted to the game's time (HANDOVER 59, scripts\fps_counters.txt): main only. The list
            # names stores of build\fps_sites.txt, which the census scanner writes; without it the lift is unchanged.
            if ($m -eq 'main') {
                $counters = Join-Path $PSScriptRoot 'fps_counters.txt'
                if (Test-Path $counters) {
                    $sitesPath = Join-Path $build 'fps_sites.txt'
                    if (Test-Path $sitesPath) { $sitesArg += @('--fps-sites', $sitesPath, '--fps-counters', $counters) }
                    else { Write-Host 'counters: build\fps_sites.txt is missing: run scripts\build-census.ps1 -Rescan first' }
                }
            }
            & $py -m nxrecomp lift $src $out --game xc2ns2 --name $m --base $base --jobs $Jobs @sitesArg 2>&1 |
                ForEach-Object { Write-Host "  $_" }
            if ($LASTEXITCODE -ne 0) { throw "lift failed for $m" }
            Set-Content -LiteralPath $stampFile -Value $base -Encoding ascii
            Write-Host ("lift {0} : {1:N1}s (base {2})" -f $m, $t.Elapsed.TotalSeconds, $base)
        }
    } finally { Pop-Location }
}

# ---- 2. compile ----------------------------------------------------------------------------------------
$inc = Join-Path $nx 'include'
$ccJobs = @()
foreach ($m in $mods) {
    $dir = Join-Path $liftDir $m
    $obj = Join-Path $objDir $m
    New-Item -ItemType Directory -Force -Path $obj | Out-Null
    $sources = Get-ChildItem $dir -Filter '*.cpp'
    foreach ($s in $sources) {
        $o = Join-Path $obj ($s.BaseName + '.obj')
        if ((Test-Path $o) -and ((Get-Item $o).LastWriteTime -gt $s.LastWriteTime)) { continue }
        $ccJobs += [pscustomobject]@{ Src = $s.FullName; Obj = $o; Mod = $m; Inc = $inc; Dir = $dir }
    }
}
Write-Host ("compile: {0} translation unit(s) to build" -f $ccJobs.Count)
if ($ccJobs.Count) {
    $t = [Diagnostics.Stopwatch]::StartNew()
    $res = $ccJobs | ForEach-Object -ThrottleLimit $Jobs -Parallel {
        $o = & clang-cl.exe /nologo /std:c++20 /O2 /c "/I$($_.Inc)" "/I$($_.Dir)" $_.Src "/Fo$($_.Obj)" 2>&1 | Out-String
        [pscustomobject]@{ Src = $_.Src; Exit = $LASTEXITCODE; Errors = ([regex]::Matches($o, 'error:')).Count; Log = $o }
    }
    $bad = @($res | Where-Object { $_.Exit -ne 0 })
    Write-Host ("compile: {0} ok, {1} failed, {2:N1}s" -f ($res.Count - $bad.Count), $bad.Count, $t.Elapsed.TotalSeconds)
    foreach ($b in $bad) { Write-Host ($b.Log -split "`n" | Where-Object { $_ -match 'error:' } | Select-Object -First 5) }
    if ($bad.Count) { throw 'compile failed' }
}

# ---- 3. one static library per module ------------------------------------------------------------------
$libs = @()
foreach ($m in $mods) {
    $obj = Join-Path $objDir $m
    $lib = Join-Path $libDir "$m.lib"
    New-Item -ItemType Directory -Force -Path (Split-Path $lib) | Out-Null
    $objs = Get-ChildItem $obj -Filter '*.obj' | ForEach-Object { '"' + $_.FullName + '"' }
    $rsp = Join-Path $objDir "$m.rsp"
    Set-Content -LiteralPath $rsp -Value $objs -Encoding ascii
    if ((Test-Path $lib) -and ((Get-Item $lib).LastWriteTime -gt (Get-ChildItem $obj -Filter '*.obj' | Sort-Object LastWriteTime -Descending | Select-Object -First 1).LastWriteTime)) {
        Write-Host "lib $m : up to date"
    } else {
        & llvm-lib.exe /nologo "/OUT:$lib" "@$rsp"
        if ($LASTEXITCODE -ne 0) { throw "llvm-lib failed for $m" }
        Write-Host ("lib {0} : {1:N1} MB" -f $m, ((Get-Item $lib).Length / 1MB))
    }
    $libs += $lib
}

# ---- 4. stub main + link -------------------------------------------------------------------------------
$stubObj = Join-Path $build 'obj\stub'
New-Item -ItemType Directory -Force -Path $stubObj | Out-Null
foreach ($s in Get-ChildItem (Join-Path $root 'src') -Filter '*.cpp' | Where-Object { $_.Name -in @('stub_main.cpp', 'rt_stub.cpp') }) {
    $o = Join-Path $stubObj ($s.BaseName + '.obj')
    if ((Test-Path $o) -and ((Get-Item $o).LastWriteTime -gt $s.LastWriteTime)) { continue }
    & clang-cl.exe /nologo /std:c++20 /O2 /c "/I$inc" $s.FullName "/Fo$o"
    if ($LASTEXITCODE -ne 0) { throw "compile failed: $($s.Name)" }
}
$binDir = Join-Path $build 'bin'
New-Item -ItemType Directory -Force -Path $binDir | Out-Null
$exe = Join-Path $binDir 'xc2ns2_stub.exe'
$linkRsp = Join-Path $build 'obj\link.rsp'
$lines = @()
$lines += (Get-ChildItem $stubObj -Filter '*.obj' | ForEach-Object { '"' + $_.FullName + '"' })
$lines += $libs | ForEach-Object { '"' + $_ + '"' }
Set-Content -LiteralPath $linkRsp -Value $lines -Encoding ascii
& clang-cl.exe /nologo "/Fe:$exe" "@$linkRsp"
if ($LASTEXITCODE -ne 0) { throw 'link failed' }
Write-Host ("link: {0} ({1:N1} MB)" -f $exe, ((Get-Item $exe).Length / 1MB))

$sw.Stop()
Write-Host ("total: {0:N1}s" -f $sw.Elapsed.TotalSeconds)
if ($Run) {
    Write-Host ''
    & $exe
    if ($LASTEXITCODE -ne 0) { throw "smoke test failed (exit $LASTEXITCODE)" }
}

