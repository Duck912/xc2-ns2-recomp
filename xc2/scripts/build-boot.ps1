# SPDX-License-Identifier: GPL-3.0-or-later
# Build xc2_boot.exe: maps the four modules, registers them with nxrt, starts the NVN back end and enters rtld.
#
#   .\scripts\build-boot.ps1                 # build
#   .\scripts\build-boot.ps1 -Run            # build and run (window)
#   .\scripts\build-boot.ps1 -Run -Gfx headless
#
# Prerequisites (built once; see docs/BUILD.md):
#   third_party\fefw-recomp\build\runtime-gfx\{nxrt.lib,nxrt_gfx.lib,...}   (graphics shell)
#   third_party\fefw-recomp\build\xc2-game-probe\games\xc2ns2\*.lib         (game module)
#   xc2\build\lib\{main,sdk,subsdk0,rtld}.lib                               (scripts\build.ps1)
#   .\scripts\build-boot.ps1 -MainLib build\lib-census\main.lib -OutDir build\boot-census   # the census build
param(
    [string]$Exefs = '',
    [string]$Link = 'host',
    [string]$Gfx = 'window',
    [switch]$Run,
    [string]$MainLib = '',      # the main.lib to link; default build\lib\main.lib
    [string]$OutDir = '',       # where xc2_boot.exe and its object go; default build\boot
    [string]$LibDir = '',       # directory holding the per-module libs build.ps1 writes; default build\lib
    [string]$Defines = ''       # extra /D defines for xc2_boot.cpp, space separated (HANDOVER 89: XC2_MODULES_7)
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
# The four NSOs now live in the project (xc2\game\xc2ns2), copied from <fefw-recomp>\work\xc2ns2.
if (-not $Exefs) { $Exefs = Join-Path $root 'game\xc2ns2' }
elseif (-not [System.IO.Path]::IsPathRooted($Exefs)) { $Exefs = Join-Path (Get-Location).Path $Exefs }
if (-not (Test-Path $Exefs)) { throw "ExeFS not found: $Exefs (copy main, sdk, subsdk0, rtld, main.npdm into xc2\game\xc2ns2)" }
# Optional: a script that puts clang-cl / llvm-lib / dotnet on PATH. A machine that already has them needs nothing.
if ($env:XC2_ENV) {
    if (-not (Test-Path $env:XC2_ENV)) { throw "XC2_ENV points at a file that does not exist: $env:XC2_ENV" }
    . $env:XC2_ENV | Out-Null
}

$repo = Split-Path -Parent $root
$rt = Join-Path $repo 'third_party\fefw-recomp'
# Not $gfx: PowerShell variable names are case-insensitive, so a variable called $gfx would overwrite the -Gfx parameter.
$gfxDir = Join-Path $rt 'build\runtime-gfx'
$game = Join-Path $rt 'build\xc2-game-probe\games\xc2ns2'
$nxinc = Join-Path $repo 'third_party\nxrecomp\recomp\include'
# Everything below switches directories for the link, so these have to be absolute from here on.
$bd = if ($OutDir) { $OutDir } else { Join-Path $root 'build\boot' }
if (-not [System.IO.Path]::IsPathRooted($bd)) { $bd = Join-Path (Get-Location).Path $bd }
$mainlib = if ($MainLib) { $MainLib } else { Join-Path $root 'build\lib\main.lib' }
if (-not [System.IO.Path]::IsPathRooted($mainlib)) { $mainlib = Join-Path (Get-Location).Path $mainlib }
$libdir = if ($LibDir) { $LibDir } else { Join-Path $root 'build\lib' }
if (-not [System.IO.Path]::IsPathRooted($libdir)) { $libdir = Join-Path (Get-Location).Path $libdir }
# The retail 3.0.1 ExeFS has three more modules (HANDOVER 89). They are linked only when their libs are in $LibDir, so the
# 4-module dev/playable build links exactly what it always did.
$extraLibs = @()
foreach ($m in 'subsdk1', 'subsdk2', 'subsdk3') { $p = Join-Path $libdir ($m + '.lib'); if (Test-Path $p) { $extraLibs += $p } }
New-Item -ItemType Directory -Force -Path $bd | Out-Null

$need = @(
    "$gfxDir\nxrt.lib", "$gfxDir\nxrt_gfx.lib", "$gfxDir\nxrt_imgui.lib", "$gfxDir\nxrt_volk.lib",
    "$gfxDir\nxrt_tiling.lib", "$gfxDir\nxrt_astc2bc7.lib", "$gfxDir\nxrt_zstd.lib",
    "$gfxDir\_deps\sdl3-build\SDL3-static.lib", "$gfxDir\third_party\dav1d\nxrt_dav1d.lib",
    "$game\nxrt_game_xc2ns2_core.lib", "$game\nxrt_game_xc2ns2_data.lib",
    $mainlib, (Join-Path $libdir 'sdk.lib'),
    (Join-Path $libdir 'subsdk0.lib'), (Join-Path $libdir 'rtld.lib')
)
foreach ($f in $need) { if (-not (Test-Path $f)) { throw "missing $f (build it first: docs\BUILD.md, then scripts\build.ps1)" } }

$obj = Join-Path $bd 'xc2_boot.obj'
$objOpus = Join-Path $bd 'x2_opus301.obj'
$objAudio = Join-Path $bd 'x2_audio301.obj'
$deps = Join-Path $repo 'third_party\deps\src'
$volk = Join-Path $deps 'volk\volk-vulkan-sdk-1.4.363.0'
$vkinc = Join-Path $deps 'vkheaders\Vulkan-Headers-vulkan-sdk-1.4.363.0\include'
$vma = Join-Path $deps 'vma\VulkanMemoryAllocator-3.4.0\include'
$sdlinc = Join-Path $deps 'sdl3\SDL3-3.4.18\include'
$defArgs = @()
if ($Defines) { foreach ($d in $Defines.Split(' ')) { if ($d) { $defArgs += "/D$d" } } }
& clang-cl.exe /nologo /std:c++20 /O2 /MT /c (Join-Path $root 'src\xc2_boot.cpp') "/Fo$obj" @defArgs `
    "/I$nxinc" "/I$rt\runtime\include" "/I$rt\runtime\games" "/I$volk" "/I$vkinc" "/I$vma" "/I$sdlinc"
if ($LASTEXITCODE -ne 0) { throw 'compile failed: xc2_boot.cpp' }
& clang-cl.exe /nologo /std:c++20 /O2 /MT /c (Join-Path $root 'src\x2_opus301.cpp') "/Fo$objOpus" @defArgs `
    "/I$nxinc" "/I$rt\runtime\include" "/I$rt\runtime\games" "/I$volk" "/I$vkinc" "/I$vma" "/I$sdlinc"
if ($LASTEXITCODE -ne 0) { throw 'compile failed: x2_opus301.cpp' }
& clang-cl.exe /nologo /std:c++20 /O2 /MT /c (Join-Path $root 'src\x2_audio301.cpp') "/Fo$objAudio" @defArgs `
    "/I$nxinc" "/I$rt\runtime\include" "/I$rt\runtime\games" "/I$volk" "/I$vkinc" "/I$vma" "/I$sdlinc"
if ($LASTEXITCODE -ne 0) { throw 'compile failed: x2_audio301.cpp' }

$exe = Join-Path $bd 'xc2_boot.exe'
& clang-cl.exe /nologo /MT "/Fe:$exe" $obj $objOpus $objAudio `
    "$gfxDir\nxrt_gfx.lib" "$gfxDir\nxrt.lib" "$game\nxrt_game_xc2ns2_core.lib" "$game\nxrt_game_xc2ns2_data.lib" `
    $mainlib (Join-Path $libdir 'sdk.lib') `
    (Join-Path $libdir 'subsdk0.lib') (Join-Path $libdir 'rtld.lib') @extraLibs `
    "$gfxDir\nxrt_imgui.lib" "$gfxDir\nxrt_volk.lib" "$gfxDir\nxrt_tiling.lib" "$gfxDir\nxrt_astc2bc7.lib" "$gfxDir\nxrt_zstd.lib" `
    "$gfxDir\_deps\sdl3-build\SDL3-static.lib" "$gfxDir\third_party\dav1d\nxrt_dav1d.lib" `
    kernel32.lib user32.lib gdi32.lib winmm.lib imm32.lib ole32.lib oleaut32.lib version.lib uuid.lib advapi32.lib `
    setupapi.lib shell32.lib dinput8.lib psapi.lib
if ($LASTEXITCODE -ne 0) { throw 'link failed' }
Write-Host ("boot exe: {0} ({1:N1} MB)" -f $exe, ((Get-Item $exe).Length / 1MB))

if ($Run) {
    Push-Location $bd
    try { & $exe --exefs $Exefs --link $Link --gfx $Gfx --log (Join-Path $bd 'xc2_boot.log') } finally { Pop-Location }
}

