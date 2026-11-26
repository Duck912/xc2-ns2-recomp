# SPDX-License-Identifier: GPL-3.0-or-later
# Assembles the XC:DE release package: the launcher, the runtime as a DLL (with n2den's NVN-HLE in it), the bundled
# Python and Zig that recompile the player's own dump, and the setup engine. A player unpacks it and installs nothing.
#
#   pwsh tools\build\build-release.ps1 -N2denDist <NVN-HLE dist> -SkipHarness -SkipExe -Zig <zig.exe>   # DLL + Python
#   pwsh tools\build\make-package-xcde.ps1 -Out D:\dist\xcde-package -Zig <zig folder>
#
# What it does NOT contain: any game file. The exe (xcde.exe) is built on the player's PC from their own dump. XC2's
# package also carries the shader harness and spirv-val; XC:DE needs neither (NVN-HLE translates shaders at run time).
param(
    [string]$Out = '',
    [string]$Zig = '',        # the Zig 0.17.0 folder (holds zig.exe); default $env:XC2_ZIG or zig.exe on PATH
    [string]$NvnhleDist = ''  # the NVN-HLE distribution folder whose LICENSES/ ship with the DLL
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # the checkout
if (-not $Out) { $Out = Join-Path (Split-Path -Parent $root) 'xcde-package' }
if (-not $Zig) {
    if ($env:XC2_ZIG) { $Zig = if (Test-Path $env:XC2_ZIG -PathType Leaf) { Split-Path -Parent $env:XC2_ZIG } else { $env:XC2_ZIG } }
    elseif ($zigCmd = Get-Command zig.exe -ErrorAction SilentlyContinue) { $Zig = Split-Path -Parent $zigCmd.Source }
}
if (-not $NvnhleDist) { $NvnhleDist = Join-Path $root 'work\nvnhle-dist' }

function Say($text) { Write-Host ("  " + $text) }
function Need($path, $what) { if (-not (Test-Path $path)) { throw "missing $what : $path" } }
function CopyTree($src, $dst) {
    New-Item -ItemType Directory -Force (Split-Path $dst -Parent) | Out-Null
    $null = robocopy $src $dst /E /SL /NFL /NDL /NJH /NJS /NP   # robocopy: the Zig tree carries symlinks
    if ($LASTEXITCODE -ge 8) { throw ("robocopy failed ($LASTEXITCODE) copying " + $src) }
}
function Size($path) { [math]::Round(((Get-ChildItem $path -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB), 1) }
function Put($rel) {   # a file of the checkout, at the same path in the package
    $dst = Join-Path $Out $rel
    New-Item -ItemType Directory -Force (Split-Path $dst -Parent) | Out-Null
    Copy-Item (Join-Path $root $rel) $dst -Force
}

Write-Host "package -> $Out"
if (Test-Path $Out) { Say 'removing the previous one'; [System.IO.Directory]::Delete($Out, $true) }
New-Item -ItemType Directory -Force $Out | Out-Null

# --- the launcher ---------------------------------------------------------------------------------------------------
$launcher = Join-Path $root 'launcher\src-tauri\target\release\xcde-launcher.exe'
Need $launcher 'the built launcher (launcher: npm run tauri build -- --no-bundle)'
Copy-Item $launcher $Out -Force
Say ("launcher      {0:N1} MB" -f ((Get-Item $launcher).Length / 1MB))

# --- the runtime: xc2_rt.dll with NVN-HLE, and its import library (Zig links the exe against it) ---------------------
$dll = Join-Path $root 'xc2\build\release\dll\xc2_rt.dll'
$lib = Join-Path $root 'xc2\build\release\dll\xc2_rt.lib'
Need $dll 'xc2_rt.dll (tools\build\build-release.ps1 -N2denDist ...)'
Need $lib 'xc2_rt.lib'
New-Item -ItemType Directory -Force (Join-Path $Out 'runtime') | Out-Null
Copy-Item $dll, $lib (Join-Path $Out 'runtime') -Force
Say ("runtime       {0:N1} MB  (xc2_rt.dll with NVN-HLE + the import library)" -f (((Get-Item $dll).Length + (Get-Item $lib).Length) / 1MB))

# --- the tools that recompile the dump --------------------------------------------------------------------------------
$py = Join-Path $root 'xc2\build\release\tools\python'
Need (Join-Path $py 'python.exe') 'the embeddable Python (tools\build\build-release.ps1)'
CopyTree $py (Join-Path $Out 'tools\python')
Say ("python        {0:N1} MB  (capstone, lz4, zstandard, nxrecomp)" -f (Size (Join-Path $Out 'tools\python')))
Need (Join-Path $Zig 'zig.exe') 'zig.exe (-Zig)'
CopyTree $Zig (Join-Path $Out 'tools\build\zig')
Say ("zig           {0:N1} MB" -f (Size (Join-Path $Out 'tools\build\zig')))

# --- the engine and what the lift and link read ----------------------------------------------------------------------
New-Item -ItemType Directory -Force (Join-Path $Out 'engine') | Out-Null
Copy-Item (Join-Path $root 'tools\setup\xcde_setup.py'), (Join-Path $root 'tools\setup\xc2_setup.py') (Join-Path $Out 'engine') -Force
Put 'tools\analysis\nup_extract.py'    # the --nup path, run with the bundled Python
Put 'tools\mods\exefs_patch.py'        # code mods (the package lift applies them when a mods/ folder exists)
New-Item -ItemType Directory -Force (Join-Path $Out 'xcde\sites') | Out-Null
Copy-Item (Join-Path $root 'xcde\sites\*') (Join-Path $Out 'xcde\sites') -Force
Put 'xcde\supported_builds.txt'        # the launcher's dump check
Put 'xc2\src\xc2_stub.cpp'
Put 'xc2\src\xc2_modules.h'
CopyTree (Join-Path $root 'third_party\nxrecomp\recomp\include') (Join-Path $Out 'third_party\nxrecomp\recomp\include')
Say 'engine        xcde_setup.py + xc2_setup.py, nup_extract.py, site lists, the exe stub, the recompiler headers'

# --- licences -----------------------------------------------------------------------------------------------------------
$lic = Join-Path $Out 'licenses'
New-Item -ItemType Directory -Force $lic | Out-Null
foreach ($f in @('LICENSE', 'THIRD_PARTY_NOTICES.md')) { if (Test-Path (Join-Path $root $f)) { Copy-Item (Join-Path $root $f) $lic -Force } }
if (Test-Path (Join-Path $NvnhleDist 'LICENSES')) {
    CopyTree (Join-Path $NvnhleDist 'LICENSES') (Join-Path $lic 'nvnhle')
    foreach ($f in @('LICENSE.txt', 'SOURCE.txt')) { if (Test-Path (Join-Path $NvnhleDist $f)) { Copy-Item (Join-Path $NvnhleDist $f) (Join-Path $lic "nvnhle\$f") -Force } }
} else { Write-Warning "no NVN-HLE LICENSES/ in ${NvnhleDist}: the package lacks the library's third-party licences" }
@"
Bundled tools, each with its own licence:
  tools/python        Python 3.13.17 (PSF) with capstone (BSD-3), lz4 (BSD-2), zstandard (BSD-3), nxrecomp (GPL-3.0)
  tools/build/zig     Zig 0.17.0 (MIT); its bundled clang, lld and libc++ carry Apache-2.0 WITH LLVM-exception
  runtime/xc2_rt.dll  this project, the fefw-recomp runtime and n2den's NVN-HLE (GPL-3.0-or-later); the libraries
                      NVN-HLE bundles keep their own licences (licenses/nvnhle, source in licenses/nvnhle/SOURCE.txt)
"@ | Set-Content -LiteralPath (Join-Path $lic 'BUNDLED_TOOLS.txt') -Encoding utf8NoBOM

@"
XC:DE NS2 recomp - portable package
===================================

Run xcde-launcher.exe. Pick your own legally dumped copy of Xenoblade Chronicles: Definitive Edition - Nintendo
Switch 2 Edition (the .nup, or its ExeFS / RomFS / add-on folders), press Set up, then Play. Set up recompiles the
game's code on this PC with the bundled tools; nothing needs to be installed. For NVIDIA DLSS, download Streamline
from the launcher's Settings.

No game files are included. Not affiliated with or endorsed by Nintendo or Monolith Soft.
"@ | Set-Content -LiteralPath (Join-Path $Out 'README.txt') -Encoding utf8NoBOM

Say ("TOTAL         {0:N1} MB" -f (Size $Out))
Write-Host "package ready: $Out"
