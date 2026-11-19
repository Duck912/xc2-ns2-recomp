# SPDX-License-Identifier: GPL-3.0-or-later
# One line that says which build this exe is, from the build.json its builder wrote next to it.
#
#   pwsh tools\run\build-stamp.ps1 -Exe xc2\build\301\boot\xc2_boot.exe
param([Parameter(Mandatory = $true)][string]$Exe)
$manifest = Join-Path (Split-Path $Exe -Parent) 'build.json'
if (-not (Test-Path -LiteralPath $manifest)) { Write-Host 'build: no build.json next to the exe (an old build?)'; exit 0 }
try { $j = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json } catch { Write-Host ('build: unreadable build.json: ' + $manifest); exit 0 }
$c = if ($j.commit) { ([string]$j.commit).Substring(0, [Math]::Min(7, ([string]$j.commit).Length)) } else { '?' }
Write-Host ("build: {0} {1} dirty={2} {3}" -f $c, $j.profile, $j.dirty, $j.built_at)
