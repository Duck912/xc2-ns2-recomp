# Translate the blocks a dump dir holds into SPIR-V and install them into the shader cache the runtime loads.
#
#   .\install_shaders.ps1 -Dump work\shader_dump8                     # translate + install into xc2\build\boot\shader_cache\spirv
#   .\install_shaders.ps1 -Dump work\shader_dump8 -Out work\cache8 -NoInstall
param(
    [Parameter(Mandatory = $true)][string]$Dump,
    [string]$Out = '',
    [string]$Cache = '',
    [int]$Jobs = 8,
    [switch]$NoInstall
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $Cache) { $Cache = Join-Path $root 'xc2\build\boot\shader_cache\spirv' }
# Optional: a script that puts clang-cl / llvm-lib / dotnet on PATH. Unset must not throw.
if ($env:XC2_ENV) {
    if (-not (Test-Path -LiteralPath $env:XC2_ENV)) { throw "XC2_ENV points at a file that does not exist: $env:XC2_ENV" }
    . $env:XC2_ENV | Out-Null
}
$harness = Join-Path $root 'third_party\fefw-recomp\tools\shaders\build\bin\Release\net10.0\spirv_harness.dll'
if (-not (Test-Path $harness)) { throw "no harness at $harness" }
$dump = if ([System.IO.Path]::IsPathRooted($Dump)) { $Dump } else { Join-Path $root $Dump }
$out = if ($Out) { if ([System.IO.Path]::IsPathRooted($Out)) { $Out } else { Join-Path $root $Out } } else { "$dump-out" }
$before = (Get-ChildItem $Dump -Filter "code_*.bin" -ErrorAction SilentlyContinue | Measure-Object).Count
$have = (Get-ChildItem $Cache -Filter "*.spv" -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Host "dump $dump : $before blocks; cache now has $have entries"

# The output directory is scratch: a leftover .spv from an earlier run must never be installed as if this run had
# produced it, so clear it first and stop if the harness failed.
if (Test-Path $out) {
    Get-ChildItem $out -Filter '*.spv' -ErrorAction SilentlyContinue | Remove-Item -Force
    Remove-Item (Join-Path $out 'results.tsv') -Force -ErrorAction SilentlyContinue
}
dotnet $harness --batch $dump --out $out --jobs $Jobs 2>&1 | Select-Object -Last 6
if ($LASTEXITCODE -ne 0) { throw "the shader harness failed (exit $LASTEXITCODE): nothing was installed" }

$made = Get-ChildItem $out -Filter "*.spv" -ErrorAction SilentlyContinue
Write-Host "translated: $($made.Count) .spv in $out"
if (-not $NoInstall) {
    New-Item -ItemType Directory -Force -Path $Cache | Out-Null
    $new = 0
    $changed = 0
    foreach ($f in $made) {
        $dst = Join-Path $Cache $f.Name
        if (-not (Test-Path $dst)) { $new++ }
        elseif ((Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash) { $changed++ }
        Copy-Item -Force $f.FullName $dst
    }
    $after = (Get-ChildItem $Cache -Filter "*.spv" | Measure-Object).Count
    Write-Host "installed $($made.Count) ($new new, $changed replaced); the cache now has $after entries"

    # spirv.preload.pack is read before the loose .spv files, so a replaced shader stays hidden behind its old pack
    # entry. Drop the pack; the next start rebuilds it from the .spv files that are on disk now.
    $pack = $Cache + '.preload.pack'
    if ($changed -gt 0 -and (Test-Path $pack)) {
        Remove-Item -LiteralPath $pack -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath ($pack + '.new') -Force -ErrorAction SilentlyContinue
        Write-Host "spirv.preload.pack dropped: $changed shader(s) changed content and the pack shadows loose files"
    }

    # The .spv alone is not enough: the runtime reads the shader's *resources* record (which c[0] descriptor each storage
    # buffer comes from, which handle each texture comes from) out of results.tsv. Without the row the reflection falls back to
    # NvnSource::Unknown, the buffer is left unbound, and Vulkan hands the shader zeros - XC2's scene fragment shaders then draw
    # a flat sky (HANDOVER 90). Merge the rows the harness wrote, by hash.
    $res = Join-Path $out 'results.tsv'
    $cacheRes = Join-Path $Cache 'results.tsv'
    if (Test-Path $res) {
        # A re-translated hash replaces its row: the .spv above was overwritten, so the old resource record no longer
        # describes it, and keeping the old row would bind the wrong descriptors.
        $tab = [char]9
        $header = Get-Content -LiteralPath $res -TotalCount 1
        $order = New-Object System.Collections.Generic.List[string]
        $rows = @{}
        if (Test-Path $cacheRes) {
            Get-Content -LiteralPath $cacheRes | Select-Object -Skip 1 | ForEach-Object {
                if (-not $_) { return }
                $k = ($_ -split $tab)[0]
                if ($k -and -not $rows.ContainsKey($k)) { $rows[$k] = $_; $order.Add($k) }
            }
        }
        $updated = 0
        $added = 0
        Get-Content -LiteralPath $res | Select-Object -Skip 1 | ForEach-Object {
            if (-not $_) { return }
            $k = ($_ -split $tab)[0]
            if (-not $k) { return }
            if ($rows.ContainsKey($k)) {
                if ($rows[$k] -ne $_) { $rows[$k] = $_; $updated++ }
            } else { $rows[$k] = $_; $order.Add($k); $added++ }
        }
        $lines = New-Object System.Collections.Generic.List[string]
        $lines.Add($header)
        foreach ($k in $order) { $lines.Add($rows[$k]) }
        Set-Content -LiteralPath $cacheRes -Value $lines -Encoding ASCII
        Write-Host "results.tsv: $added new, $updated replaced; the cache table now has $($order.Count) hashes"
    } else {
        Write-Warning "no results.tsv next to the translated .spv: the runtime will not know this shader's resources"
    }
}
