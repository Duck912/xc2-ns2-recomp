# Translate the blocks a run could not find, and retype the samplers the run reported, so the next launch is complete.
# Called by play-301.cmd after the game exits: the blocks the game asked for and the cache lacked are already on disk,
# so this costs a translation of a handful of shaders, not another run.
param(
    [Parameter(Mandatory = $true)][string]$Cache,
    [Parameter(Mandatory = $true)][string]$Missing,
    [string]$Harness = '',
    [string]$DsLog = ''
)
$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent

# The launcher does not set XC2_PYTHON, and "python" is not on PATH on a machine that only installed the toolchain
# through the env script. Say so once instead of failing inside build_cache with an unexplained exit code.
function Test-Python([string]$p) {
    # The Windows Store alias (WindowsApps\python.exe) exists on PATH, does nothing, and returns an error, so
    # "it is on PATH" is not enough: it has to answer --version.
    if (-not $p -or $p -match '\\WindowsApps\\') { return $false }
    try { & $p --version *> $null; return ($LASTEXITCODE -eq 0) } catch { return $false }
}
$py = $env:XC2_PYTHON
if (-not (Test-Python $py)) {
    $py = $null
    # The packaged interpreter first: a release carries tools\python with zstandard/lz4/capstone inside it.
    foreach ($cand in @((Join-Path $root 'xc2\build\release\tools\python\python.exe'),
                        (Join-Path $root 'tools\python\python.exe'))) {
        if (Test-Python $cand) { $py = $cand; break }
    }
}
if (-not $py) {
    foreach ($name in 'python', 'python3', 'py') {
        $cand = Get-Command $name -ErrorAction SilentlyContinue
        if ($cand -and (Test-Python $cand.Source)) { $py = $cand.Source; break }
    }
}
if (-not $py) {
    Write-Output 'fill-cache: no working python - set XC2_PYTHON to a python.exe and run again'
    Write-Output ('fill-cache: the blocks are kept in ' + $Missing + ' and nothing is lost')
    exit 0
}

$codes = @(Get-ChildItem $Missing -Filter 'code_*.bin' -ErrorAction SilentlyContinue)
if (-not $codes) { Write-Output 'fill-cache: nothing to do'; exit 0 }
Write-Output ("fill-cache: {0} block(s) to translate" -f $codes.Count)

# Where the translator is, in the order a player's copy would find it:
#   1. the self-contained publish (dotnet publish -r win-x64 --self-contained), which needs no .NET installed;
#   2. a release package that carries tools\spirv_harness next to the tree;
#   3. the development build, which is framework-dependent and therefore needs the .NET runtime.
if (-not $Harness) {
    foreach ($cand in @(
        (Join-Path $root 'third_party\fefw-recomp\tools\shaders\build\publish\win-x64\spirv_harness.exe'),
        (Join-Path $root 'tools\spirv_harness\spirv_harness.exe'),
        (Join-Path $root 'third_party\fefw-recomp\tools\shaders\build\bin\Release\net10.0\spirv_harness.exe'))) {
        if (Test-Path $cand) { $Harness = $cand; break }
    }
}
if (-not $Harness -or -not (Test-Path $Harness)) {
    Write-Output 'fill-cache: no spirv_harness.exe. Build it once with:'
    Write-Output '  dotnet publish third_party\fefw-recomp\tools\shaders\harness\SpirvHarness.csproj -c Release -r win-x64 --self-contained true -o third_party\fefw-recomp\tools\shaders\build\publish\win-x64'
    exit 1
}
Write-Output ("fill-cache: python " + $py)
Write-Output ("fill-cache: harness " + $Harness)

# the manifest dump_missing wrote is already in the corpus layout, so build_cache takes the folder as it is
& $py (Join-Path $root 'tools\shader\cache\build_cache.py') --blocks $Missing --cache $Cache --harness $Harness --jobs 8
if ($LASTEXITCODE -ne 0) { Write-Output 'fill-cache: build_cache failed'; exit 1 }

# the same run can tell us which samplers need their type corrected; that is what format-07753 is
if ($DsLog -and (Test-Path $DsLog)) {
    & $py (Join-Path $root 'tools\shader\patch_ds_samplers.py') --log $DsLog --cache $Cache
    if ($LASTEXITCODE -ne 0) { Write-Output 'fill-cache: patch_ds_samplers reported a problem (the cache is still complete)' }
}

# the pack is rebuilt from the cache, and a stale one would hide what we just added
$pack = Join-Path (Split-Path $Cache -Parent) 'spirv.preload.pack'
if (Test-Path $pack) { Remove-Item $pack -Force }

# keep the blocks: a reporter can send them, and a re-run must not look like new work
$done = Join-Path (Split-Path $Cache -Parent) 'filled'
New-Item -ItemType Directory -Force $done | Out-Null
Move-Item (Join-Path $Missing '*') $done -Force
Write-Output ("fill-cache: done, blocks kept in " + $done)
