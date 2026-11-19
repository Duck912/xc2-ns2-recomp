<#
    patch-shaders.ps1 -- install the hand-patched shaders after build-shaders.ps1 rewrote the cache.

      .\patch-shaders.ps1            # copy every patch in xc2\game\shader-patch into the cache
      .\patch-shaders.ps1 -Check     # report only (exit 1 when a patch is not in the cache, or is shadowed by the preload pack)

    Each patch is <hash16>.spv (+ the .frag it was built from, for the record). A patch must keep the shader's
    interface: the runtime refuses anything else. See HANDOVER 37 (2649526f) and 40.37 (57bdd1a0).

    THE PRELOAD PACK SHADOWS THE CACHE (HANDOVER 40.37.5): the runtime reads shader_cache\spirv.preload.pack first
    and only falls back to <hash>.spv for hashes the pack lacks; the pack's per-entry line_hash only tracks
    results.tsv, so an edited .spv is never picked up while its (old) frame is in the pack. Installing a patch
    therefore also has to drop the pack: the next start re-reads the .spv files and writes a fresh one.
#>
param([switch]$Check)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
# The patches are derived from the game's own shaders, so they are not distributed with this repository: the
# folder is yours to create (see docs/BUILD.md 4.4). A missing folder is not an error.
$src = if ($env:XC2_PATCH_DIR) { $env:XC2_PATCH_DIR } else { Join-Path $root 'xc2\patches' }
$cache = Join-Path $root 'xc2\build\boot\shader_cache\spirv'
$pack = $cache + '.preload.pack'
if (-not (Test-Path $src)) {
    Write-Host "no patch folder: $src (patches are derived from the game's shaders and are not distributed; nothing to do)"
    exit 0
}
if (-not (Test-Path $cache)) { throw "no shader cache: $cache (build first)" }

# hash -> uncompressed size of the SPIR-V the pack would hand out (the pack is read before any .spv file).
function Read-PackSizes([string]$path) {
    $sizes = @{}
    if (-not (Test-Path $path)) { return $sizes }
    $fs = [System.IO.File]::Open($path, 'Open', 'Read', 'ReadWrite')
    try {
        $head = New-Object byte[] 32
        if ($fs.Read($head, 0, 32) -ne 32) { return $sizes }
        if ([System.Text.Encoding]::ASCII.GetString($head, 0, 8) -ne 'NXSPACK1') { return $sizes }
        $count = [BitConverter]::ToUInt32($head, 12)
        $indexOffset = [BitConverter]::ToUInt64($head, 16)
        if ($count -eq 0 -or $count -gt 1000000) { return $sizes }
        $fs.Position = [long]$indexOffset
        $idx = New-Object byte[] ($count * 40)
        $read = 0
        while ($read -lt $idx.Length) {
            $n = $fs.Read($idx, $read, $idx.Length - $read)
            if ($n -le 0) { return @{} }
            $read += $n
        }
        for ($i = 0; $i -lt $count; $i++) {
            $o = $i * 40
            $hash = [System.Text.Encoding]::ASCII.GetString($idx, $o, 16).TrimEnd([char]0)
            $sizes[$hash] = [BitConverter]::ToUInt32($idx, $o + 36)
        }
    } finally { $fs.Dispose() }
    return $sizes
}

$packSizes = Read-PackSizes $pack
$packNote = if (Test-Path $pack) { "preload.pack: $($packSizes.Count) shaders" } else { "preload.pack: absent (rebuilt from the .spv files at the next start)" }

$n = 0; $bad = 0; $stale = @()
foreach ($f in [System.IO.Directory]::GetFiles($src, '*.spv')) {
    $name = Split-Path -Leaf $f
    $dst = Join-Path $cache $name
    $len = (Get-Item $f).Length
    # Content, not length: a recompiled patch usually keeps the size and only the bytes change.
    $same = $false
    if (Test-Path $dst) {
        $same = (Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash
    }
    $hash = [System.IO.Path]::GetFileNameWithoutExtension($name)
    # The pack is read before the loose .spv, so any entry for this hash shadows the patch, whatever its size.
    $shadow = $packSizes.ContainsKey($hash)
    if ($Check) {
        if ($same -and -not $shadow) { Write-Host ("  ok        " + $name) }
        elseif (-not $same) { Write-Host ("  PATCH     " + $name) -ForegroundColor Yellow; $bad++ }
        else {
            Write-Host ("  SHADOWED  " + $name + "  (spirv.preload.pack still has this hash and is read before the loose .spv; the install drops the pack)") -ForegroundColor Yellow
            $bad++
        }
        continue
    }
    Copy-Item $f $dst -Force
    $n++
    if ($shadow) { $stale += $hash }
    Write-Host ("installed " + $name)
}
Write-Host $packNote
if ($Check) { exit ([int]($bad -gt 0)) }

if ($stale.Count -gt 0) {
    $removed = @()
    foreach ($p in @($pack, $pack + '.new')) {
        if (Test-Path $p) { Remove-Item $p -Force; $removed += (Split-Path -Leaf $p) }
    }
    Write-Host ("dropped " + ($removed -join ', ') + ": it still held the unpatched " + ($stale -join ', ') +
                " and the runtime reads the pack before the .spv files. The next start re-reads the .spv files and writes a new pack.")
} elseif (Test-Path $pack) {
    Write-Host "the preload pack already matches these patches"
}
Write-Host "$n shader patch(es) installed into $cache"
