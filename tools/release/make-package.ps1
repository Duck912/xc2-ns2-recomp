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
# The launcher must be built with `npm run tauri build -- --no-bundle`, never with a bare `cargo build`: the CLI is
# what embeds the frontend, and a cargo build produces an exe that looks for the dev server on 127.0.0.1:1420 instead
# (2026-11-18: shipped like that once, every player saw ERR_CONNECTION_REFUSED). The frontend bundle it embeds must be
# newer than its sources, which is what the CLI guarantees and a hand-run cargo build does not.
$dist = Join-Path (Split-Path -Parent $Launcher) 'dist\index.html'
if (Test-Path $dist) {
    if ((Get-Item $exe).LastWriteTime -lt (Get-Item $dist).LastWriteTime) {
        throw "the launcher ($exe) is older than its frontend ($dist): rebuild it with 'npm run tauri build -- --no-bundle'"
    }
}
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
# spirv-val: the harness validates every translation with it, and a machine without the Vulkan SDK has none - the
# shader step then died with an unhandled Win32Exception (issue #5, 2026-11-18). SPIRV-Tools, Apache-2.0.
if (-not $SkipHarness) {
    $val = ''
    if ($env:VULKAN_SDK) { $val = Join-Path $env:VULKAN_SDK 'Bin\spirv-val.exe' }
    if (-not $val -or -not (Test-Path $val)) {
        $cand = Get-ChildItem 'C:\VulkanSDK' -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending |
                ForEach-Object { Join-Path $_.FullName 'Bin\spirv-val.exe' } | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($cand) { $val = $cand }
    }
    if (-not $val -or -not (Test-Path $val)) {
        $cmd = Get-Command spirv-val.exe -ErrorAction SilentlyContinue
        if ($cmd) { $val = $cmd.Source }
    }
    Need $val 'spirv-val.exe (the Vulkan SDK installs it; the package ships it so players need none)'
    New-Item -ItemType Directory -Force (Join-Path $Out 'tools\spirv-val') | Out-Null
    Copy-Item $val (Join-Path $Out 'tools\spirv-val\spirv-val.exe') -Force
    # Apache-2.0 section 4 wants a copy of the licence with the binary, not a pointer to it.
    $lic = Join-Path $root 'licenses\Apache-2.0.txt'
    Need $lic 'licenses\Apache-2.0.txt'
    $head = @'
spirv-val.exe - part of SPIRV-Tools, https://github.com/KhronosGroup/SPIRV-Tools
Copyright (c) The Khronos Group Inc. Licensed under the Apache License, Version 2.0.
This is an unmodified copy of the binary that ships with the Vulkan SDK (LunarG), redistributed so that the shader
harness can validate translated shaders on a machine that has no Vulkan SDK installed.
The full licence text follows.

--------------------------------------------------------------------------------

'@
    Set-Content -LiteralPath (Join-Path $Out 'tools\spirv-val\LICENSE.txt') -Value $head -Encoding utf8
    Add-Content -LiteralPath (Join-Path $Out 'tools\spirv-val\LICENSE.txt') -Value (Get-Content $lic -Raw) -Encoding utf8
    Say ("spirv-val     {0:N1} MB  (Apache-2.0, validates every translated shader)" -f ((Get-Item $val).Length / 1MB))
}
Need (Join-Path $Zig 'zig.exe') 'zig.exe'
CopyTree $Zig (Join-Path $Out 'tools\build\zig')
Say ("zig           {0:N1} MB" -f (Size (Join-Path $Out 'tools\build\zig')))

# --- 3b. what this folder is, so a player who unzips it has somewhere to start --------------------------------
Copy-Item (Join-Path $PSScriptRoot 'PACKAGE-README.txt') (Join-Path $Out 'README.txt') -Force

# --- 4. the engine, the shader corpus extractor, and what the lift needs --------------------------------------
New-Item -ItemType Directory -Force (Join-Path $Out 'engine') | Out-Null
Copy-Item (Join-Path $root 'tools\setup\xc2_setup.py') (Join-Path $Out 'engine') -Force
# The shader chain: the game's shaders are embedded in the romfs's bf2.ard, which these read and translate. Without
# them a package has an empty cache and the first launch renders with gaps.
New-Item -ItemType Directory -Force (Join-Path $Out 'tools\shader-cache') | Out-Null
Copy-Item (Join-Path $root 'tools\shader-cache\*.py') (Join-Path $Out 'tools\shader-cache') -Force
# The stencil-plane retype (format-07753): the prefill runs with ds_debug and this rewrites the samplers it names.
# Without it in the package a first run renders characters and the background untextured.
New-Item -ItemType Directory -Force (Join-Path $Out 'tools\shader') | Out-Null
Copy-Item (Join-Path $root 'tools\shader\patch_ds_samplers.py') (Join-Path $Out 'tools\shader') -Force
# The engine's --nup path runs this with the bundled Python (zstandard is in it), for a player whose dump is a .nup.
New-Item -ItemType Directory -Force (Join-Path $Out 'tools\analysis') | Out-Null
Copy-Item (Join-Path $root 'tools\analysis\nup_extract.py') (Join-Path $Out 'tools\analysis') -Force
Say 'engine        xc2_setup.py + the shader chain + nup_extract.py'
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
