# Install the repository's git hooks into .git/hooks.
#
#   pwsh -File tools/install-git-hooks.ps1
#
# The hooks live in tools/git-hooks so they are versioned; .git/hooks is not.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$src = Join-Path $root 'tools\git-hooks'
$dst = Join-Path $root '.git\hooks'
if (-not (Test-Path $dst)) { throw "no .git/hooks: is this a checkout? ($dst)" }
Get-ChildItem $src -File | ForEach-Object {
    $target = Join-Path $dst $_.Name
    Copy-Item -LiteralPath $_.FullName -Destination $target -Force
    Write-Host ("installed " + $_.Name)
}
Write-Host "hooks installed into $dst"
