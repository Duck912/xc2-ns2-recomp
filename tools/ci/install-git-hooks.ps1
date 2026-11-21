# Install the repository's git hooks into .git/hooks.
#
#   pwsh -File tools/ci/install-git-hooks.ps1
#
# The hooks live in tools/ci/hooks so they are versioned; .git/hooks is not.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # tools\ci -> the checkout
$src = Join-Path $root 'tools\ci\hooks'
$dst = Join-Path $root '.git\hooks'
if (-not (Test-Path $dst)) { throw "no .git/hooks: is this a checkout? ($dst)" }
Get-ChildItem $src -File | ForEach-Object {
    $target = Join-Path $dst $_.Name
    Copy-Item -LiteralPath $_.FullName -Destination $target -Force
    Write-Host ("installed " + $_.Name)
}
Write-Host "hooks installed into $dst"
