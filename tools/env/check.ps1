# tools\env\check.ps1 - verify (and repair) everything this project's toolchain needs.
#
#   .\tools\env\check.ps1              check, and repair what can be repaired from local copies
#   .\tools\env\check.ps1 -CheckOnly   report only, change nothing
#
# Why: the lift needs lz4/capstone/unicorn inside the DSH python, and every fresh session used to
# rediscover that by hitting ModuleNotFoundError halfway through a build. This answers
# "is the environment complete" in one call, and copies those packages from the venv that already
# sits on this machine instead of downloading them.
#
# Exit code: 0 = everything present, 1 = something is missing (see the MISSING line).
param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$py = if ($env:XC2_PYTHON) { $env:XC2_PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { (Get-Command python).Source } else { '' }
$pysite = if ($py) { Join-Path (Split-Path -Parent $py) 'Lib\site-packages' } else { '' }
$venvsite = '<fefw-recomp>\work\las-recon\venv\Lib\site-packages'
$script:missing = @()

function Row([bool]$ok, [string]$what, [string]$detail) {
    $tag = 'MISS'
    if ($ok) { $tag = 'OK  ' } else { $script:missing += $what }
    Write-Host ('  [{0}] {1,-26} {2}' -f $tag, $what, $detail)
}

Write-Host ''
Write-Host '== host toolchain ($env:XC2_ENV) =='
$envps = $env:XC2_ENV
Row (Test-Path $envps) 'env.ps1' $envps
if (Test-Path $envps) { . $envps | Out-Null }
foreach ($c in 'cmake','ninja','clang-cl','llvm-objdump','llvm-mc','llvm-cxxfilt','nasm','dotnet','git') {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    $d = 'not on PATH after env.ps1'
    if ($cmd) { $d = Split-Path -Leaf $cmd.Source }
    Row ([bool]$cmd) $c $d
}

Write-Host ''
Write-Host '== python (the lifter runs on this one) =='
Row (Test-Path $py) 'python' $py
if (Test-Path $py) {
    Row $true 'python version' (& $py -c "import sys; print('%d.%d.%d' % sys.version_info[:3])")
    # required by the lift / the project's own tools
    $pkgs = [ordered]@{ 'lz4.block' = 'lz4'; 'capstone' = 'capstone'; 'unicorn' = 'unicorn'; 'zstandard' = 'zstandard' }
    # optional: only the upstream survey tools (third_party\nxrecomp\tools\*) import pyelftools
    $opt = [ordered]@{ 'elftools' = 'elftools' }
    foreach ($m in $pkgs.Keys) {
        & $py -c "import $m" 2>$null | Out-Null
        $ok = ($LASTEXITCODE -eq 0)
        $note = 'import ok'
        if (-not $ok) {
            $note = 'pip install needed (no local copy)'
            $src = Join-Path $venvsite $pkgs[$m]
            if ((-not $CheckOnly) -and (Test-Path $src) -and (Test-Path $pysite)) {
                Copy-Item -Recurse -Force $src (Join-Path $pysite $pkgs[$m])
                & $py -c "import $m" 2>$null | Out-Null
                $ok = ($LASTEXITCODE -eq 0)
                if ($ok) { $note = 'copied from the local venv' }
            }
        }
        Row $ok $m $note
    }
    foreach ($m in $opt.Keys) {
        & $py -c "import $m" 2>$null | Out-Null
        $ok = ($LASTEXITCODE -eq 0)
        $note = 'optional, only upstream survey tools need it'
        if ($ok) { $note = 'present (optional)' }
        $tag = 'OK  '
        if (-not $ok) { $tag = 'opt ' }
        Write-Host ('  [{0}] {1,-26} {2}' -f $tag, $m, $note)
    }
}

Write-Host ''
Write-Host '== game data (read-only, never in git) =='
$exefs = Join-Path $repo 'xc2\game\xc2ns2'
foreach ($f in 'main','sdk','subsdk0','rtld','main.npdm') {
    $p = Join-Path $exefs $f
    $d = 'missing'
    if (Test-Path $p) { $d = '{0:N0} B' -f (Get-Item $p).Length }
    Row (Test-Path $p) ('exefs/' + $f) $d
}
foreach ($r in 'romfs','romfs-pkg0') {
    $ard = Join-Path $repo ('xc2\build\boot\game\' + $r + '\bf2.ard')
    $d = 'missing'
    if (Test-Path $ard) { $d = '{0:N0} B bf2.ard' -f (Get-Item $ard).Length }
    Row (Test-Path $ard) ('romfs/' + $r) $d
}

Write-Host ''
Write-Host '== build artifacts =='
$lift = Join-Path $repo 'xc2\build\lift\main'
$n = (Get-ChildItem $lift -Filter 'module_*.cpp' -ErrorAction SilentlyContinue | Measure-Object).Count
Row ($n -gt 0) 'lift/main' "$n module_*.cpp"
$lib = Join-Path $repo 'xc2\build\lib\main.lib'
$d = 'run xc2\scripts\build.ps1'
if (Test-Path $lib) { $d = '{0:N1} MB' -f ((Get-Item $lib).Length / 1MB) }
Row (Test-Path $lib) 'lib/main.lib' $d
$boot = Join-Path $repo 'xc2\build\boot\xc2_boot.exe'
$d = 'run xc2\scripts\build-boot.ps1'
if (Test-Path $boot) { $d = '{0:N1} MB, {1}' -f ((Get-Item $boot).Length / 1MB), (Get-Item $boot).LastWriteTime.ToString('yyyy-MM-dd HH:mm') }
Row (Test-Path $boot) 'xc2_boot.exe' $d

Write-Host ''
if ($script:missing.Count) {
    Write-Host ('MISSING ({0}): {1}' -f $script:missing.Count, ($script:missing -join ', '))
    exit 1
}
Write-Host 'environment complete.'
exit 0
