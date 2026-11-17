# SPDX-License-Identifier: GPL-3.0-or-later
# Assembles the portable tree: the launcher, the runtime as a DLL, and the two tools that compile the lifted code, so
# a player unpacks it and needs nothing installed - no MSVC, no Windows SDK, no Python, no .NET, no Zig.
#
#   pwsh tools\release\make-package.ps1 -Out E:\XC2-package
#
# What it does NOT contain: any game file. The exe is built on the player's PC from their own dump (that is the whole
# point of the recompilation), and the shader cache is translated from their own shaders.
param(
    [string]$Out = '',
    [string]$Launcher = 'E:\XC2-launcher',
    [string]$Zig = 'E:\Tools\dev\zig',
    [switch]$SkipHarness,
    [switch]$SkipPython
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # the checkout
if (-not $Out) { $Out = Join-Path (Split-Path -Parent $root) 'XC2-package' }

function Say($text) { Write-Host ("  " + $text) }
function Need($path, $what) { if (-not (Test-Path $path)) { throw "missing $what : $path" } }

# robocopy, not Copy-Item: the Zig distribution carries symlinks and Copy-Item leaves a half-built tree behind.
function CopyTree($src, $dst) {
    New-Item -ItemType Directory -Force (Split-Path $dst -Parent) | Out-Null
    $null = robocopy $src $dst /E /SL /NFL /NDL /NJH /NJS /NP
    if ($LASTEXITCODE -ge 8) { throw ("robocopy failed ($($LASTEXITCODE)) copying " + $src) }
}
function RemoveTree($p) {
    if (-not (Test-Path $p)) { return }
    try { [System.IO.Directory]::Delete($p, $true) } catch { Remove-Item $p -Recurse -Force -ErrorAction SilentlyContinue }
}
function Size($path) {
    try {
        $s = (Get-ChildItem $path -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
        if ($s) { return [math]::Round($s / 1MB, 1) }
    } catch { }
    return 0
}

Write-Host "package -> $Out"
if (Test-Path $Out) { Say 'removing the previous one'; RemoveTree $Out }
New-Item -ItemType Directory -Force $Out | Out-Null

# --- 1. the launcher ---------------------------------------------------------------------------------------------
$exe = Join-Path $Launcher 'src-tauri\target\release\xc2-launcher.exe'
Need $exe 'the built launcher'
Copy-Item $exe $Out -Force
Say ("launcher      {0:N1} MB" -f ((Get-Item $exe).Length / 1MB))

# --- 2. the runtime, as a DLL and the import library to link against ---------------------------------------------
$dll = Join-Path $root 'xc2\build\rt-dll\xc2_rt.dll'
$lib = Join-Path $root 'xc2\build\rt-dll\xc2_rt.lib'
Need $dll 'xc2_rt.dll (pwsh xc2\scripts\build-release.ps1)'
Need $lib 'xc2_rt.lib'
New-Item -ItemType Directory -Force (Join-Path $Out 'runtime') | Out-Null
Copy-Item $dll, $lib (Join-Path $Out 'runtime') -Force
Say ("runtime       {0:N1} MB  (xc2_rt.dll + the import library)" -f (((Get-Item $dll).Length + (Get-Item $lib).Length) / 1MB))

# --- 3. the tools: an embeddable Python with the lifter in it, the shader harness, Zig -----------------------------
$py = Join-Path $root 'xc2\build\release\tools\python'
if (-not $SkipPython) {
    Need (Join-Path $py 'python.exe') 'the embeddable Python (pwsh xc2\scripts\build-release.ps1)'
    CopyTree $py (Join-Path $Out 'tools\python')
    Say ("python        {0:N1} MB  (capstone, lz4, zstandard, nxrecomp)" -f (Size (Join-Path $Out 'tools\python')))
}
$harness = Join-Path $root 'third_party\fefw-recomp\tools\shaders\build\publish\win-x64'
if (-not $SkipHarness) {
    Need (Join-Path $harness 'spirv_harness.exe') 'the published shader harness'
    CopyTree $harness (Join-Path $Out 'tools\spirv_harness')
    Say ("harness       {0:N1} MB  (self-contained, no .NET)" -f (Size (Join-Path $Out 'tools\spirv_harness')))
}
Need (Join-Path $Zig 'zig.exe') 'zig.exe'
CopyTree $Zig (Join-Path $Out 'tools\build\zig')
Say ("zig           {0:N1} MB" -f (Size (Join-Path $Out 'tools\build\zig')))

# --- 4. the engine, the shader corpus extractor, and what the lift needs --------------------------------------
New-Item -ItemType Directory -Force (Join-Path $Out 'engine') | Out-Null
Copy-Item (Join-Path $root 'tools\setup\xc2_setup.py') (Join-Path $Out 'engine') -Force
New-Item -ItemType Directory -Force (Join-Path $Out 'tools\shaders') | Out-Null
Copy-Item (Join-Path $root 'third_party\fefw-recomp\tools\shaders\ampere\extract_corpus.py') (Join-Path $Out 'tools\shaders') -Force
Say 'engine        xc2_setup.py + extract_corpus.py'
New-Item -ItemType Directory -Force (Join-Path $Out 'xc2\sites') | Out-Null
Copy-Item (Join-Path $root 'xc2\sites\*.txt') (Join-Path $Out 'xc2\sites') -Force
New-Item -ItemType Directory -Force (Join-Path $Out 'xc2\src') | Out-Null
Copy-Item (Join-Path $root 'xc2\src\xc2_stub.cpp'), (Join-Path $root 'xc2\src\xc2_modules.h') (Join-Path $Out 'xc2\src') -Force
CopyTree (Join-Path $root 'third_party\nxrecomp\recomp\include') (Join-Path $Out 'third_party\nxrecomp\recomp\include')
Say ("sources       {0:N1} MB  (hook tables, recompiler headers, the exe stub)" -f ((Size (Join-Path $Out 'xc2')) + (Size (Join-Path $Out 'third_party'))))

# --- 5. licences -------------------------------------------------------------------------------------------------
$lic = Join-Path $Out 'licenses'
New-Item -ItemType Directory -Force $lic | Out-Null
foreach ($f in @('LICENSE', 'THIRD_PARTY_NOTICES.md')) {
    $src = Join-Path $root $f
    if (Test-Path $src) { Copy-Item $src $lic -Force }
}
$notes = @"
XC2 NS2 recomp - portable package
=================================

Run xc2-launcher.exe. It asks for your own legally dumped copy of the game, recompiles it on this PC and plays it.

Nothing here is derived from the game. The exe is built on your PC from your own dump; the shader cache is
translated from your own shaders. The runtime DLL and the tools below are our own code or third-party code.

Bundled tools, each with its own licence:
  tools/python         Python 3.13.17 (PSF) with capstone (BSD-3), lz4 (BSD-2), zstandard (BSD-3), nxrecomp (GPL-3.0)
  tools/spirv_harness  Ryujinx's shader translator (MIT) in a self-contained .NET 10 runtime (MIT)
  tools/build/zig      Zig 0.17.0 (MIT); its bundled clang, lld and libc++ carry Apache-2.0 WITH LLVM-exception
  runtime/xc2_rt.dll   this project and the fefw-recomp runtime (GPL-3.0-or-later)
"@
Set-Content -LiteralPath (Join-Path $lic 'BUNDLED_TOOLS.txt') -Value $notes -Encoding utf8NoBOM

Say ("TOTAL         {0:N1} MB" -f (Size $Out))
Write-Host "package ready: $Out"
