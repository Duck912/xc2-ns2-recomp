# SPDX-License-Identifier: GPL-3.0-or-later
# Start the game from a profile: config/profiles/<name>.ini holds every path and switch, this script applies them.
#
#   pwsh tools\run\play.ps1 -Profile dev
#   pwsh tools\run\play.ps1 -Profile dev -Fps 30 -Headless -Seconds 40
#
# The profile is data: the same engine can start the development build, a packaged install or an A/B run without
# another .cmd file full of set lines. tools\run\play-301.cmd is now a shim over this script.
param(
    [string]$Profile = 'dev',
    [string]$ProfileFile = '',
    [int]$Fps = 0,
    [switch]$Headless,
    [switch]$NoPrefill,
    [switch]$Dump,
    [string]$Shots = '',
    [int]$Seconds = 0,
    [string]$Exe = '',
    [string]$Log = '',
    [hashtable]$Env = @{}
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # tools\run -> the checkout
if (-not $ProfileFile) { $ProfileFile = Join-Path $repo ("config\\profiles\\" + $Profile + ".ini") }
if (-not (Test-Path -LiteralPath $ProfileFile)) { throw "no profile at $ProfileFile" }

# A small ini reader: [section], key = value, # and ; comments. Paths resolve against the checkout.
$cfg = @{}
$section = ''
foreach ($line in Get-Content -LiteralPath $ProfileFile) {
    $l = $line.Trim()
    if (-not $l -or $l.StartsWith('#') -or $l.StartsWith(';')) { continue }
    if ($l -match '^\[(.+)\]$') { $section = $matches[1].Trim(); continue }
    $i = $l.IndexOf('=')
    if ($i -lt 1) { continue }
    $cfg[$section + '/' + $l.Substring(0, $i).Trim()] = $l.Substring($i + 1).Trim()
}
function Get-Cfg([string]$key, [string]$fallback = '') {
    if ($cfg.ContainsKey($key)) { return $cfg[$key] }
    return $fallback
}
function Resolve-Under([string]$value) {
    if (-not $value) { return '' }
    if ([System.IO.Path]::IsPathRooted($value)) { return $value }
    return (Join-Path $repo $value)
}

$exe = if ($Exe) { $Exe } else { Resolve-Under (Get-Cfg 'run/exe') }
$cwd = Resolve-Under (Get-Cfg 'run/cwd')
$exefs = Resolve-Under (Get-Cfg 'run/exefs')
$romfs = Resolve-Under (Get-Cfg 'run/romfs')
$dlc = Resolve-Under (Get-Cfg 'run/dlc')
$save = Resolve-Under (Get-Cfg 'run/save')
$cache = Resolve-Under (Get-Cfg 'run/shader_cache')
$missing = Resolve-Under (Get-Cfg 'run/missing')
$logs = Resolve-Under (Get-Cfg 'run/logs')
$gf = if ($Headless) { 'headless' } else { Get-Cfg 'run/gfx' 'window' }
$fps = if ($Fps -gt 0) { $Fps } else { [int](Get-Cfg 'run/fps' '60') }
$hz = [int](Get-Cfg 'run/hz' '60')
if (-not (Test-Path -LiteralPath $exe)) { throw "no exe at $exe (build it first: tools\\build\\build-boot.ps1)" }
if (-not (Test-Path -LiteralPath $cwd)) { throw "no working directory at $cwd" }
foreach ($d in $logs, $missing, $save) { if ($d) { New-Item -ItemType Directory -Force -Path $d | Out-Null } }

foreach ($k in $cfg.Keys) {
    if ($k.StartsWith('env/')) { Set-Item -Path ('env:' + $k.Substring(4)) -Value $cfg[$k] }
}
foreach ($k in $Env.Keys) { Set-Item -Path ('env:' + $k) -Value $Env[$k] }
$env:NXRT_XC2_FPS = "$fps"
$env:NXRT_NVN_PRESENT_INTERVAL_HZ = "$hz"
$env:NXRT_FS_ROMFS = $romfs
$env:NXRT_FS_SAVE_DIR = $save
$env:NXRT_AOC_DIR = $dlc
$env:NXRT_NVN_SHADER_CACHE = $cache
$env:NXRT_NVN_DUMP_MISSING = $missing
$env:NXRT_NVN_SKIP_FS_FILE = Join-Path $repo 'work\\skip_fs.txt'
$env:NXRT_NVN_HOT_STATE_FILE = Join-Path $repo 'work\\hot_state.txt'
if (-not (Test-Path -LiteralPath $env:NXRT_NVN_SKIP_FS_FILE)) { New-Item -ItemType File -Path $env:NXRT_NVN_SKIP_FS_FILE -Force | Out-Null }
if (-not (Test-Path -LiteralPath $env:NXRT_NVN_HOT_STATE_FILE)) { Set-Content -LiteralPath $env:NXRT_NVN_HOT_STATE_FILE -Value ('front_face=' + (Get-Cfg 'env/NXRT_NVN_FRONT_FACE_MODE' '2')) }
if ($Dump) { New-Item -ItemType Directory -Force -Path $missing | Out-Null; $env:NXRT_NVN_DUMP_ALL = '1' }

# The upscaler hot file: start every run from the ini, never from what a previous session left behind.
$hot = Join-Path $repo 'work\\dlss_hot.txt'
Set-Content -LiteralPath $hot -Value 'upscaler = taau' -Encoding ascii
$env:NXRT_DLSS_HOT_FILE = $hot

# The preload pack is read before the loose .spv files, so a pack older than a replaced shader hides it.
$pack = Join-Path (Split-Path $cache -Parent) 'spirv.preload.pack'
if (Test-Path -LiteralPath $pack) { Remove-Item -LiteralPath $pack -Force }

if (-not $Log) {
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $Log = Join-Path $logs ('play-' + $stamp + '.log')
}
if ($Shots) {
    $dir = Join-Path $repo ('work\\shots\\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $env:NXRT_NVN_SHOT_FRAMES = $Shots
    $env:NXRT_NVN_SHOT_DIR = $dir
    Write-Host "shots: $dir"
}

if (-not $NoPrefill -and -not $env:XC2_NOPREFILL) {
    & pwsh -NoProfile -File (Join-Path $repo 'tools\\run\\prefill.ps1') -Exe $exe -Exefs $exefs -Cache $cache -Work (Join-Path $repo 'work')
}
if (-not $exefs -or -not (Test-Path -LiteralPath $exefs)) { throw "no exefs at $exefs" }
if (-not (Test-Path -LiteralPath $romfs)) { throw "no romfs at $romfs" }

& pwsh -NoProfile -File (Join-Path $repo 'tools\\run\\build-stamp.ps1') -Exe $exe
Write-Host ("profile {0}: {1} at {2} fps" -f $Profile, $exe, $fps)
Push-Location $cwd
try {
    $argv = @('--exefs', $exefs, '--link', (Get-Cfg 'run/link' 'host'), '--gfx', $gf, '--log', $Log)
    if ($Seconds -gt 0) {
        $p = Start-Process -FilePath $exe -ArgumentList $argv -PassThru -NoNewWindow
        Write-Host ("pid {0}; stopping after {1}s" -f $p.Id, $Seconds)
        Start-Sleep -Seconds $Seconds
        if (-not $p.HasExited) { $p.Kill(); $p.WaitForExit(5000) | Out-Null }
    } else {
        & $exe @argv
    }
} finally { Pop-Location }
Write-Host "log: $Log"
