# Stage the three Ryujinx projects the translator needs into tools\shaders\third_party\ryubing (git-ignored).
#
# Source: the Ryubing fork of Ryujinx, commit a82350bb77 (MIT). Nothing of it is stored in this repository - it is either
# a local checkout (-Ryubing) or, when that is missing, downloaded from the project's own Forgejo archive below. That
# archive is the only external source this build needs besides the recompiler and CMake's FetchContent deps.
#
# The build writes obj/bin next to the sources, so we stage a copy and never touch the checkout.
param(
    [string]$Ryubing = (Join-Path $PSScriptRoot '..\..\..\refs\ryubing'),
    [string]$Archive = 'https://git.ryujinx.app/projects/Ryubing/archive/a82350bb774f70fcbd41c9987bf67a3775409963.tar.gz'
)
$ErrorActionPreference = 'Stop'

if (-not (Test-Path (Join-Path $Ryubing 'src\Ryujinx.Common'))) {
    Write-Host "Ryujinx sources not found at $Ryubing; downloading the archive"
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ('ryubing-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
    New-Item -ItemType Directory -Force $tmp | Out-Null
    $tgz = Join-Path $tmp 'ryubing.tar.gz'
    try {
        if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
            & curl.exe -sSL --fail --retry 3 --retry-delay 2 -o $tgz $Archive
            if ($LASTEXITCODE -ne 0) { throw "curl exit $LASTEXITCODE" }
        } else {
            $old = $ProgressPreference
            $ProgressPreference = 'SilentlyContinue'
            Invoke-WebRequest -Uri $Archive -OutFile $tgz -UseBasicParsing
            $ProgressPreference = $old
        }
        if (-not (Test-Path $tgz) -or (Get-Item $tgz).Length -lt 100000) { throw 'the archive is missing or truncated' }
        & tar -xzf $tgz -C $tmp
        if ($LASTEXITCODE -ne 0) { throw "tar exit $LASTEXITCODE" }
        $Ryubing = Join-Path $tmp 'ryubing'
        if (-not (Test-Path (Join-Path $Ryubing 'src\Ryujinx.Common'))) { throw "the archive did not contain src\Ryujinx.Common" }
        Write-Host ("  extracted {0:N1} MB from {1}" -f ((Get-Item $tgz).Length / 1MB), $Archive)
    } catch {
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
        throw ("could not obtain the Ryujinx sources: " + $_.Exception.Message +
               ". Pass -Ryubing <checkout> if you already have one.")
    }
}

# robocopy does not create intermediate directories when the destination still contains '..': it exits 16 and copies
# nothing, which is what a clean checkout hits (the workspace already had the folders).
$dst = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\third_party\ryubing'))
New-Item -ItemType Directory -Force "$dst\src" | Out-Null
foreach ($p in 'Ryujinx.Common','Spv.Generator','Ryujinx.Graphics.Shader') {
    robocopy "$Ryubing\src\$p" "$dst\src\$p" /MIR /XD obj bin /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy $p failed ($LASTEXITCODE)" }
}
foreach ($f in 'Directory.Build.props','Directory.Packages.props','global.json','nuget.config','LICENSE.txt') {
    Copy-Item "$Ryubing\$f" "$dst\$f" -Force
}
Write-Host "staged Ryujinx sources in $dst"
$global:LASTEXITCODE = 0
