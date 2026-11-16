# make-portable.ps1 -- assemble a self-contained XC2 run directory for another PC / another card.
#
#   .\make-portable.ps1 -Destination <drive>:\xc2-portable          # full copy (~10.7 GB)
#   .\make-portable.ps1 -Destination <drive>:\xc2-portable -Mode hardlink  # same volume, instant
#   .\make-portable.ps1 -Destination D:\t -SkipRomfs                 # layout test only
#
# What it writes (mirrors the project layout so play.cmd works unchanged):
#
#   <dst>\play.cmd
#   <dst>\xc2\scripts\play.ps1
#   <dst>\xc2\build\boot\xc2_boot.exe
#   <dst>\xc2\build\boot\shader_order.txt
#   <dst>\xc2\build\boot\shader_cache\spirv\        (9,029 .spv + results.tsv)
#   <dst>\xc2\build\boot\shader_cache\spirv.preload.pack
#   <dst>\xc2\build\boot\game\romfs\                 (bf2.arh + bf2.ard, 10.45 GB)
#   <dst>\xc2\game\xc2ns2\                           (ExeFS)
#
# Deliberately NOT copied: *.preload.pack.new (it would replace the pack at the next start),
# pipeline_cache.bin / pipeline_keys.bin (bound to the GPU and driver version -- let the target
# machine build its own), logs, trace PNGs, screenshots, save data.
param(
    [Parameter(Mandatory=$true)][string]$Destination,
    [ValidateSet('copy','hardlink')][string]$Mode = 'copy',
    [switch]$SkipRomfs
)
$ErrorActionPreference = 'Stop'
$xc2 = Split-Path -Parent $PSScriptRoot          # <project>\xc2
$root = Split-Path -Parent $xc2                  # <project>
$boot = Join-Path $xc2 'build\boot'
$cache = Join-Path $boot 'shader_cache\spirv'
$pack = Join-Path $boot 'shader_cache\spirv.preload.pack'
$order = Join-Path $boot 'shader_order.txt'
$results = Join-Path $cache 'results.tsv'

function Put($src, $dst) {
    $d = Split-Path -Parent $dst
    if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
    if (Test-Path -LiteralPath $dst) { Remove-Item -LiteralPath $dst -Force }
    if ($Mode -eq 'hardlink') {
        New-Item -ItemType HardLink -Path $dst -Target $src -Force | Out-Null
    } else {
        Copy-Item -LiteralPath $src -Destination $dst -Force
    }
}

Write-Host "preflight" -ForegroundColor Cyan
foreach ($p in @($pack, $order, $results, (Join-Path $boot 'xc2_boot.exe'), (Join-Path $root 'xc2\game\xc2ns2'))) {
    if (-not (Test-Path -LiteralPath $p)) { throw "missing: $p" }
}
$spv = Get-ChildItem -LiteralPath $cache -Filter '*.spv'
$rows = (Get-Content -LiteralPath $results | Measure-Object -Line).Lines - 1
$pb = [System.IO.File]::ReadAllBytes($pack)
$magic = [System.Text.Encoding]::ASCII.GetString($pb, 0, 8)
if ($magic -ne 'NXSPACK1') { throw "pack magic is '$magic', not NXSPACK1" }
$count = [BitConverter]::ToUInt32($pb, 12)   # PackHeader: magic[8], version, count
Write-Host ("  .spv {0}   results rows {1}   pack entries {2}   pack {3:N1} MB" -f $spv.Count, $rows, $count, ($pb.Length/1MB))
if ($count -lt 1) { throw "pack is empty" }
if (Test-Path -LiteralPath ($pack + '.new')) { Write-Host "  note: a .new staging file exists and will NOT be copied" -ForegroundColor Yellow }

Write-Host "writing $Destination ($Mode)" -ForegroundColor Cyan
Put (Join-Path $root 'play.cmd') (Join-Path $Destination 'play.cmd')
Put (Join-Path $root 'xc2\scripts\play.ps1') (Join-Path $Destination 'xc2\scripts\play.ps1')
Put (Join-Path $boot 'xc2_boot.exe') (Join-Path $Destination 'xc2\build\boot\xc2_boot.exe')
Put $order (Join-Path $Destination 'xc2\build\boot\shader_order.txt')
Put $pack (Join-Path $Destination 'xc2\build\boot\shader_cache\spirv.preload.pack')
Put $results (Join-Path $Destination 'xc2\build\boot\shader_cache\spirv\results.tsv')
foreach ($f in Get-ChildItem -LiteralPath (Join-Path $root 'xc2\game\xc2ns2') -File) {
    Put $f.FullName (Join-Path $Destination ('xc2\game\xc2ns2\' + $f.Name))
}
$n = 0
foreach ($f in $spv) {
    Put $f.FullName (Join-Path $Destination ('xc2\build\boot\shader_cache\spirv\' + $f.Name))
    $n++
    if ($n % 2000 -eq 0) { Write-Host ("  .spv {0}/{1}" -f $n, $spv.Count) }
}
if (-not $SkipRomfs) {
    $romfs = Join-Path $boot 'game\romfs'
    foreach ($f in Get-ChildItem -LiteralPath $romfs -File) {
        Write-Host ("  romfs {0} ({1:N0} MB)" -f $f.Name, ($f.Length/1MB))
        Put $f.FullName (Join-Path $Destination ('xc2\build\boot\game\romfs\' + $f.Name))
    }
}

$readme = @"
XC2 static recompilation -- portable run directory
built $(Get-Date -Format 'yyyy-MM-dd HH:mm')

Run:  double-click play.cmd   (or: pwsh -File xc2\scripts\play.ps1 -PresentHz 60)

Needs a Vulkan 1.3 GPU. The first start on a new machine builds pipeline_cache.bin and
pipeline_keys.bin beside xc2_boot.exe -- that is expected; a few frames will hitch while it does.

What is here
  xc2\build\boot\xc2_boot.exe                 the recompiled runtime
  xc2\build\boot\shader_cache\spirv\          $($spv.Count) SPIR-V modules + results.tsv
  xc2\build\boot\shader_cache\spirv.preload.pack   $count shaders in one file, read front to back at boot
  xc2\build\boot\shader_order.txt             $((Get-Content -LiteralPath $order | Measure-Object -Line).Lines) hashes preloaded at boot
  xc2\build\boot\game\romfs\                  bf2.arh + bf2.ard
  xc2\game\xc2ns2\                            ExeFS (main, sdk, subsdk0, rtld, main.npdm)

What is deliberately absent
  *.preload.pack.new    would replace the pack at the next start
  pipeline_cache.bin    bound to one GPU + driver version; the target builds its own
  logs, trace PNGs, screenshots, save data

Save data lives in %APPDATA%\Xenoblade2NS2RecompPC\save -- copy it across if you want the
same playthrough.
"@
Set-Content -LiteralPath (Join-Path $Destination 'README.txt') -Value $readme -Encoding UTF8
$sz = (Get-ChildItem -LiteralPath $Destination -Recurse -File | Measure-Object Length -Sum)
Write-Host ("done: {0:N0} files, {1:N2} GB" -f $sz.Count, ($sz.Sum/1GB)) -ForegroundColor Green
