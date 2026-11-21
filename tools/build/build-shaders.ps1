# build-shaders.ps1 -- one command that makes the shader cache and the preload pack complete.
#
#   .\build-shaders.ps1 -Check        # report only; exit 1 if anything is missing
#   .\build-shaders.ps1               # rescan, translate what is missing, install, repack, verify
#   .\build-shaders.ps1 -NoRescan     # reuse the last scan (skips ~75 s of census)
#   .\build-shaders.ps1 -Jobs 16      # translation parallelism (default 10)
#
# What "complete" means for this title (HANDOVER 34):
#   archive  bf2.ard      5 .wishp libraries + every program embedded in resource files
#   ExeFS    main/sdk/... engine shaders hardcoded in .rodata (LZ4-compressed in the NSO)
#   universe 9,022 code areas -- all translated, all in shader_cache\spirv, all in the pack
#
# The script does not touch shader_order.txt: that is the preload list, and the runtime maintains
# it itself.  The pack holds everything; boot reads it front to back, so an on-demand read is a
# page-cache hit.
param(
    [switch]$Check,
    [switch]$NoRescan,
    [int]$Jobs = 10
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$xc2 = Join-Path $root 'xc2'
$driver = Join-Path $root 'work\oracle\build_shaders.py'
if (-not (Test-Path $driver)) { throw "missing $driver" }

$envScript = $env:XC2_ENV   # optional: a script that puts clang-cl / llvm-lib / dotnet on PATH
if (Test-Path $envScript) { . $envScript | Out-Null }
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw 'python not on PATH (set $env:XC2_PYTHON, or source $env:XC2_ENV)' }

$args = @($driver)
if ($Check)    { $args += '--check' }
if ($NoRescan) { $args += '--no-rescan' }
$args += @('--jobs', "$Jobs")

& $python @args
exit $LASTEXITCODE
