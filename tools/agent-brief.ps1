# agent-brief.ps1 -- print everything a fresh session needs, in one screen.
#
#   pwsh -File tools/agent-brief.ps1
#
# A new session has no memory of this project. This prints the four things that rebuild the judgement:
# the current state, the decisions that are already settled, where the code is, and what changed last.
# Read it before touching anything.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$internal = Join-Path $root 'docs\internal'

function Section([string]$title) {
    Write-Host ''
    Write-Host ('=' * 72) -ForegroundColor DarkGray
    Write-Host $title -ForegroundColor Cyan
    Write-Host ('=' * 72) -ForegroundColor DarkGray
}

Section 'XC2 NS2 recomp -- agent brief'

Write-Host ''
Write-Host 'Repository : ' -NoNewline; Write-Host $root
Push-Location $root
try {
    $branch = git rev-parse --abbrev-ref HEAD 2>$null
    $head = git log --oneline -1 2>$null
    $dirty = (git status --porcelain | Measure-Object -Line).Lines
    Write-Host ('Branch     : ' + $branch)
    Write-Host ('HEAD       : ' + $head)
    Write-Host ('Working    : ' + $(if ($dirty -eq 0) { 'clean' } else { "$dirty changed file(s)" }))

    Section 'CURRENT STATE  (docs/internal/STATE.md)'
    $state = Join-Path $internal 'STATE.md'
    if (Test-Path $state) { Get-Content $state } else { Write-Host '  MISSING: ' $state -ForegroundColor Red }

    Section 'SETTLED DECISIONS  (docs/internal/DECISIONS.md, last 12)'
    $dec = Join-Path $internal 'DECISIONS.md'
    if (Test-Path $dec) {
        (Get-Content $dec | Where-Object { $_ -match '^- ' } | Select-Object -Last 12) | ForEach-Object { '  ' + $_ }
    } else { Write-Host '  MISSING: ' $dec -ForegroundColor Red }

    Section 'RECENT HISTORY  (last 8 commits)'
    git log --oneline -8 | ForEach-Object { '  ' + $_ }

    Section 'WHAT YOU MUST NOT DO'
    @(
        'The game runs in one instance and the operator starts and stops it. Never kill it.',
        'The shader cache is append-only: never rebuild or delete xc2\build\boot\shader_cache.',
        'Nothing from docs/internal, work/, xc2/game or xc2/build may ever be committed.',
        'Use absolute paths in PowerShell: relative paths break when the working directory moves.'
    ) | ForEach-Object { '  - ' + $_ }

    Section 'BEFORE YOU FINISH'
    @(
        '1. Overwrite docs/internal/STATE.md (one screen: what works, what is in flight, what is next).',
        '2. If you settled something, append one line to docs/internal/DECISIONS.md.',
        '3. Write the round into docs/internal/handover/NN-<date>-<topic>.md.',
        '4. pwsh -File tools/check_invariants.ps1 equivalent: python tools/check_invariants.py'
    ) | ForEach-Object { '  ' + $_ }

    Write-Host ''
} finally { Pop-Location }
