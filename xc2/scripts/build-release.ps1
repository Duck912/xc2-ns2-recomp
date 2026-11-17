# SPDX-License-Identifier: GPL-3.0-or-later
# Build the release split: xc2_rt.dll (runtime + boot code, a C ABI, no game code) and xc2_boot.exe (a stub plus
# the libraries lifted from the player's own dump, compiled by the bundled Zig).
#
#   pwsh xc2\scripts\build-release.ps1                       # everything, into xc2\build\release
#   pwsh xc2\scripts\build-release.ps1 -SkipDll              # only compile the lift and link the exe
#   pwsh xc2\scripts\build-release.ps1 -Zig D:\zig\zig.exe -Jobs 6
#
# The lift has to exist first (xc2\scripts\build.ps1). Nothing from the game is in the DLL; nothing from the
# runtime is in the exe. Upstream ships the same arrangement as fefw_rt.dll + fefw.exe.
param(
    [string]$Zig = '',
    [int]$Jobs = 0,
    [string]$OutDir = '',
    [string]$DllBuildDir = '',
    [string]$LiftDir = '',
    [switch]$SkipDll,
    [switch]$SkipExe,
    [switch]$SkipHarness
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot            # xc2
$repo = Split-Path -Parent $root                    # the checkout
$rt = Join-Path $repo 'third_party\fefw-recomp'

if ($env:XC2_ENV) { if (-not (Test-Path $env:XC2_ENV)) { throw "XC2_ENV points at a file that does not exist: $env:XC2_ENV" }; . $env:XC2_ENV | Out-Null }
if (-not $Jobs -or $Jobs -lt 1) { $Jobs = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors - 1; if ($Jobs -lt 2) { $Jobs = 2 } }
if (-not $OutDir) { $OutDir = Join-Path $root 'build\release' }
if (-not $DllBuildDir) { $DllBuildDir = Join-Path $root 'build\rt-dll' }
if (-not $LiftDir) { $LiftDir = Join-Path $root 'build\lift-301' }

# The bundled Zig is what makes this build need no MSVC and no Windows SDK: it carries its own headers and CRT.
if (-not $Zig) {
    foreach ($cand in @($env:XC2_ZIG, (Join-Path $repo 'third_party\fefw-recomp\game-build\release\zig\zig.exe'), 'E:\Tools\dev\zig\zig.exe')) {
        if ($cand -and (Test-Path $cand)) { $Zig = $cand; break }
    }
    if (-not $Zig) {
        $onPath = Get-Command zig.exe -ErrorAction SilentlyContinue
        if ($onPath) { $Zig = $onPath.Source }
    }
}
if (-not $Zig -or -not (Test-Path $Zig)) { throw 'no zig.exe: pass -Zig, set $env:XC2_ZIG, or put it on PATH' }
Write-Host ("zig: {0} ({1})" -f $Zig, (& $Zig version))

$modules = @('main', 'sdk', 'subsdk0', 'subsdk1', 'subsdk2', 'subsdk3', 'rtld')
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# ---- 1. xc2_rt.dll --------------------------------------------------------------------------------------
$dll = Join-Path $DllBuildDir 'xc2_rt.dll'
if (-not $SkipDll) {
    $t = [Diagnostics.Stopwatch]::StartNew()
    $cfg = @('-S', (Join-Path $root 'release'), '-B', $DllBuildDir, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
             '-DCMAKE_C_COMPILER=clang-cl', '-DCMAKE_CXX_COMPILER=clang-cl')
    # Reuse the runtime's fetched third-party sources instead of downloading them again.
    $deps = Join-Path $rt 'build\runtime-gfx\_deps'
    if (Test-Path $deps) { $cfg += "-DFETCHCONTENT_BASE_DIR=$deps" }
    & cmake @cfg 2>&1 | ForEach-Object { if ($_ -match 'error|Error') { Write-Host "  $_" } }
    if ($LASTEXITCODE -ne 0) { throw 'the release project could not be configured' }
    & cmake --build $DllBuildDir --target xc2_rt 2>&1 | ForEach-Object { if ($_ -match 'error|Linking|undefined') { Write-Host "  $_" } }
    if ($LASTEXITCODE -ne 0) { throw 'xc2_rt.dll did not build' }
    Write-Host ("xc2_rt.dll: {0:N1} MB in {1:N0} s" -f ((Get-Item $dll).Length / 1MB), $t.Elapsed.TotalSeconds)
} elseif (-not (Test-Path $dll)) { throw "no $dll and -SkipDll was given" }

# ---- 0. the shader translator, published self-contained -----------------------------------------------
# Framework-dependent would need the .NET runtime on the player's machine; this carries its own. Nothing in it is
# derived from the game: it is Ryujinx's translator (MIT) plus our own harness code, and it reads the shader
# bytecode from the dump at run time.
if (-not $SkipHarness) {
    $proj = Join-Path $rt 'tools\shaders\harness\SpirvHarness.csproj'
    $pub = Join-Path $rt 'tools\shaders\build\publish\win-x64'
    # Prefer the SDK the environment script points at: a bare 'dotnet' on PATH is often a runtime-only install and
    # then 'dotnet publish' answers "No .NET SDKs were found".
    $dn = $null
    foreach ($cand in @((Join-Path $env:DOTNET_ROOT 'dotnet.exe'), 'dotnet')) {
        if (-not $cand) { continue }
        $exe = if ($cand -eq 'dotnet') { (Get-Command dotnet -ErrorAction SilentlyContinue).Source } else { $cand }
        if ($exe -and (Test-Path $exe) -and (& $exe --list-sdks 2>$null)) { $dn = $exe; break }
    }
    if (-not $dn) { throw 'no .NET SDK found: set $env:DOTNET_ROOT or put the SDK on PATH' }
    $t = [Diagnostics.Stopwatch]::StartNew()
    & $dn publish $proj -c Release -r win-x64 --self-contained true -p:PublishSingleFile=false -o $pub 2>&1 |
        ForEach-Object { if ($_ -match 'error|-> ') { Write-Host "  $_" } }
    if ($LASTEXITCODE -ne 0) { throw 'the shader harness did not publish' }
    $h = Join-Path $pub 'spirv_harness.exe'
    $mb = ((Get-ChildItem $pub -Recurse -File | Measure-Object Length -Sum).Sum / 1MB)
    Write-Host ("spirv_harness: {0:N0} MB self-contained in {1:N0} s -> {2}" -f $mb, $t.Elapsed.TotalSeconds, $pub)
}

if ($SkipExe) { return }

# ---- 2. compile the lift with Zig ------------------------------------------------------------------------
$inc = Join-Path $repo 'third_party\nxrecomp\recomp\include'
$objRoot = Join-Path $root 'build\obj-zig'
$flags = @('-target', 'x86_64-windows-gnu', '-mcpu=x86_64+cx16+fma', '-std=c++20', '-O1', '-w',
           '-fno-exceptions', '-fno-rtti', '-fno-strict-aliasing', '-ffp-contract=off', '-fno-math-errno',
           '-fno-threadsafe-statics', '-DNX_INLINE_INDIRECT')
$todo = @()
foreach ($m in $modules) {
    $dir = Join-Path $LiftDir $m
    if (-not (Test-Path $dir)) { throw "no lifted sources for $m in $dir (run xc2\scripts\build.ps1 first)" }
    $od = Join-Path $objRoot $m
    New-Item -ItemType Directory -Force -Path $od | Out-Null
    foreach ($s in Get-ChildItem $dir -Filter '*.cpp') {
        $o = Join-Path $od ($s.BaseName + '.o')
        if ((Test-Path $o) -and ((Get-Item $o).LastWriteTime -gt $s.LastWriteTime)) { continue }
        $todo += [pscustomobject]@{ Src = $s.FullName; Obj = $o; Dir = $dir }
    }
}
Write-Host ("compile: {0} translation unit(s) with zig, {1} at a time" -f $todo.Count, $Jobs)
if ($todo.Count) {
    $t = [Diagnostics.Stopwatch]::StartNew()
    $res = $todo | ForEach-Object -ThrottleLimit $Jobs -Parallel {
        $o = & $using:Zig c++ @using:flags "-I$($using:inc)" "-I$($_.Dir)" -c $_.Src "-o$($_.Obj)" 2>&1 | Out-String
        [pscustomobject]@{ Src = $_.Src; Exit = $LASTEXITCODE; Log = $o }
    }
    $bad = @($res | Where-Object { $_.Exit -ne 0 })
    Write-Host ("compile: {0} ok, {1} failed, {2:N1}s" -f ($res.Count - $bad.Count), $bad.Count, $t.Elapsed.TotalSeconds)
    foreach ($b in $bad) {
        Write-Host ("  {0}: exit {1}" -f (Split-Path $b.Src -Leaf), $b.Exit)
        $lines = @($b.Log -split "`n" | Where-Object { $_ -match 'error:|fatal' } | Select-Object -First 5)
        if (-not $lines.Count) { $lines = @($b.Log -split "`n" | Where-Object { $_.Trim() } | Select-Object -First 5) }
        foreach ($l in $lines) { Write-Host ('    ' + $l.TrimEnd()) }
    }
    if ($bad.Count) { throw 'the lift did not compile' }
}

# ---- 3. link the exe: the stub + every lifted object + the DLL's import library ---------------------------
$objs = Get-ChildItem $objRoot -Recurse -Filter '*.o' | ForEach-Object { $_.FullName }
$exe = Join-Path $OutDir 'xc2_boot.exe'
# 537 object paths are about 40 kB, past the 32,767-character limit on a Windows command line, so they go in a
# response file (zig expands @file) and everything else stays on the command line.
$rsp = Join-Path $objRoot 'objects.rsp'
Set-Content -LiteralPath $rsp -Value ($objs | ForEach-Object { '"' + $_ + '"' }) -Encoding ascii
$t = [Diagnostics.Stopwatch]::StartNew()
$o = & $Zig c++ -target x86_64-windows-gnu -O1 -w -fno-exceptions -fno-rtti -DXC2_MODULES_7 "@$rsp" `
        (Join-Path $root 'src\xc2_stub.cpp') "-I$inc" "-I$(Join-Path $root 'src')" `
        (Join-Path $DllBuildDir 'xc2_rt.lib') -o $exe 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) {
    ($o -split "`n") | Where-Object { $_ -match 'error|undefined' } | Select-Object -First 10 | ForEach-Object { Write-Host ('  ' + $_.Trim()) }
    throw 'the exe did not link'
}
Copy-Item -LiteralPath $dll -Destination $OutDir -Force
Write-Host ("exe: {0:N1} MB + xc2_rt.dll, linked in {1:N0} s -> {2}" -f ((Get-Item $exe).Length / 1MB), $t.Elapsed.TotalSeconds, $OutDir)
