# agent-brief.ps1 -- print everything a fresh session needs, or verify closeout state.
#
#   pwsh -File tools/agent-brief.ps1
#   pwsh -File tools/agent-brief.ps1 -VerifyCloseout [-FixHardlink]
#   pwsh -File tools/agent-brief.ps1 [-CardPath ...] [-MaintCardPath ...]
#
# Harness-agnostic entry point for any AI session (no memory across sessions):
# prints current state, settled decisions, recent commits, guardrails, and runs closeout verification.
param(
    [switch]$VerifyCloseout,
    [switch]$FixHardlink,
    [string]$CardPath = '',
    [string]$MaintCardPath = ''
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$workspaceRoot = Split-Path -Parent $root
$driveRoot = Split-Path -Parent $workspaceRoot
$internal = Join-Path $root 'docs\internal'
$maintDir = if ($env:XC2_MAINT_DIR) { $env:XC2_MAINT_DIR } else { Join-Path $workspaceRoot 'maintenance' }
$cardName = 'XC2-开新会话先读这个.md'
$card = if ($CardPath) {
    $CardPath
} elseif ($env:XC2_ONBOARDING_CARD) {
    $env:XC2_ONBOARDING_CARD
} else {
    $candParent = if ($driveRoot) { Join-Path $driveRoot $cardName } else { '' }
    $candWs = Join-Path $workspaceRoot $cardName
    if ($candParent -and (Test-Path -LiteralPath $candParent)) { $candParent } else { $candWs }
}
$cardMaint = if ($MaintCardPath) {
    $MaintCardPath
} elseif ($env:XC2_MAINT_CARD) {
    $env:XC2_MAINT_CARD
} else {
    Join-Path $maintDir $cardName
}

function Section([string]$title) {
    Write-Host ''
    Write-Host ('=' * 72) -ForegroundColor DarkGray
    Write-Host $title -ForegroundColor Cyan
    Write-Host ('=' * 72) -ForegroundColor DarkGray
}

function Find-WorkingPython {
    $candidates = @()
    if ($env:XC2_PYTHON) { $candidates += $env:XC2_PYTHON }
    $dshPy = Join-Path $env:USERPROFILE '.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $dshPy) { $candidates += $dshPy }
    $candidates += @('python3', 'python', 'py')
    foreach ($c in $candidates) {
        if (-not $c) { continue }
        try {
            $null = & $c -c "import sys" 2>$null
            if ($LASTEXITCODE -eq 0) { return $c }
        } catch { }
    }
    return $null
}

function Get-CardCommit([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    $headLines = Get-Content -LiteralPath $path -TotalCount 12 -Encoding UTF8
    foreach ($line in $headLines) {
        if ($line -match '(?:@|HEAD)\s*`?([0-9a-f]{7,40})') {
            return $matches[1]
        }
    }
    return $null
}

Section 'XC2 NS2 recomp -- agent brief'

Write-Host ''
Write-Host 'Repository : ' -NoNewline; Write-Host $root
Push-Location $root
$failures = 0
try {
    $branch = git rev-parse --abbrev-ref HEAD 2>$null
    $headLine = git log --oneline -1 2>$null
    $headSha = git rev-parse --short HEAD 2>$null
    $dirty = (git status --porcelain | Measure-Object -Line).Lines
    Write-Host ('Branch     : ' + $branch)
    Write-Host ('HEAD       : ' + $headLine)
    Write-Host ('Working    : ' + $(if ($dirty -eq 0) { 'clean' } else { "$dirty changed file(s)" }))

    Section "ONBOARDING CARD  ($card)"
    if (Test-Path -LiteralPath $card) {
        $docCommit = Get-CardCommit $card
        $cardHead = Get-Content -LiteralPath $card -TotalCount 12 -Encoding UTF8
        $next = $cardHead | Where-Object { $_ -match '^下一步[:：]' } | Select-Object -First 1
        if ($docCommit) {
            $behind = 0
            $n = git rev-list --count "$docCommit..HEAD" 2>$null
            if ($LASTEXITCODE -eq 0 -and $n) { $behind = [int]$n }
            if ($behind -gt 5) {
                Write-Host ("  WARN   the card is $behind commits behind HEAD (at $docCommit, HEAD $headSha)") -ForegroundColor Yellow
            } else {
                Write-Host ("  ok     the card is at $docCommit ($behind commits behind HEAD)")
            }
        } else {
            Write-Host '  WARN   the card has no @<sha> / HEAD <sha> anchor line in top 12 lines' -ForegroundColor Yellow
        }
        if ($next) { Write-Host ('  ' + $next.Trim()) }
    } else {
        Write-Host ("  MISSING: $card (optional; pass -CardPath or set XC2_ONBOARDING_CARD)") -ForegroundColor Yellow
    }

    Section 'CURRENT STATE  (docs/internal/STATE.md)'
    $state = Join-Path $internal 'STATE.md'
    if (Test-Path -LiteralPath $state) {
        Get-Content -LiteralPath $state -Encoding UTF8
    } else {
        Write-Host ('  MISSING: ' + $state) -ForegroundColor Red
    }

    Section 'SETTLED DECISIONS  (docs/internal/DECISIONS.md, last 12)'
    $dec = Join-Path $internal 'DECISIONS.md'
    if (Test-Path -LiteralPath $dec) {
        (Get-Content -LiteralPath $dec -Encoding UTF8 | Where-Object { $_ -match '^([-*]|\d+\.)\s+' } | Select-Object -Last 12) |
            ForEach-Object { '  ' + $_ }
    } else {
        Write-Host ('  MISSING: ' + $dec) -ForegroundColor Red
    }

    Section 'RECENT HISTORY  (last 8 commits)'
    git log --oneline -8 | ForEach-Object { '  ' + $_ }

    Section 'WHAT YOU MUST NOT DO'
    @(
        'The game runs in one instance and the operator starts and stops it. Never kill or restart it.',
        'The shader cache is append-only: never rebuild or delete xc2\build\boot\shader_cache.',
        'Nothing from docs/internal/, work/, xc2/game/, or xc2/build/ may ever be committed.',
        'Use absolute paths in PowerShell and never run git add -A.'
    ) | ForEach-Object { '  - ' + $_ }

    Section 'BEFORE YOU FINISH (ANY HARNESS)'
    @(
        '1. Overwrite docs/internal/STATE.md (single screen: working / broken / in-flight / next).',
        '2. Append settled findings with § numbers to docs/internal/DECISIONS.md.',
        '3. Write docs/internal/handover/NN-<date>-<topic>.md and update handover/_index.json.',
        '4. Update top lines of any external onboarding card (keep hardlink to maintenance copy if used).',
        '5. Verify everything: pwsh -File tools/agent-brief.ps1 -VerifyCloseout',
        '6. Commit by path, then run your external maintenance sync script if configured.'
    ) | ForEach-Object { '  ' + $_ }

    if ($VerifyCloseout) {
        Section 'CLOSEOUT VERIFICATION'

        # 1. Check Python & run CI gates + tool tests
        $py = Find-WorkingPython
        if (-not $py) {
            Write-Host '  FAIL   no working python interpreter found (set $env:XC2_PYTHON)' -ForegroundColor Red
            $failures++
        } else {
            Write-Host "  ok     python: $py"
            $checks = @(
                @('tools/ci/check_invariants.py'),
                @('tools/ci/check_links.py'),
                @('tools/ci/config_table.py', '--check'),
                @('tools/ci/check_play_settings.py'),
                @('tools/ci/check_install_template.py'),
                @('-m', 'unittest', 'discover', '-s', 'tools/tests', '-p', 'test_*.py')
            )
            foreach ($args in $checks) {
                $label = ($args -join ' ')
                $out = & $py @args 2>&1
                if ($LASTEXITCODE -ne 0) {
                    Write-Host ("  FAIL   $label") -ForegroundColor Red
                    $out | ForEach-Object { Write-Host ('         ' + $_) }
                    $failures++
                } else {
                    Write-Host ("  ok     $label")
                }
            }
        }

        # 2. Check internal handover _index.json vs files on disk (when docs/internal exists)
        if (Test-Path -LiteralPath $internal) {
            $hdir = Join-Path $internal 'handover'
            $idxPath = Join-Path $hdir '_index.json'
            if ((Test-Path -LiteralPath $hdir) -and (Test-Path -LiteralPath $idxPath) -and $py) {
                $idxScript = @'
import json, pathlib, sys
hdir = pathlib.Path(sys.argv[1])
idx = json.loads((hdir / "_index.json").read_text(encoding="utf-8"))
entries = idx.get("files", [])
indexed = [e["file"] for e in entries]
disk = sorted(p.name for p in hdir.glob("*.md") if not p.name.startswith("_"))
missing_idx = sorted(set(disk) - set(indexed))
missing_disk = sorted(set(indexed) - set(disk))
seen_nums = {}
dups = []
for e in entries:
    for n in e.get("nums", []):
        if n in seen_nums:
            dups.append((n, seen_nums[n], e["file"]))
        else:
            seen_nums[n] = e["file"]
if missing_idx or missing_disk:
    if missing_idx: print("unindexed:", missing_idx)
    if missing_disk: print("missing_on_disk:", missing_disk)
    sys.exit(1)
if dups:
    print("WARN duplicate section nums:", dups)
print(f"synced ({len(disk)} files)")
'@
                $idxOut = $idxScript | & $py - $hdir 2>&1
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "  FAIL   handover/_index.json mismatch: $idxOut" -ForegroundColor Red
                    $failures++
                } else {
                    Write-Host "  ok     handover/_index.json: $idxOut"
                }
            }

            # 3. Check card hardlink integrity
            if ((Test-Path -LiteralPath $card) -and (Test-Path -LiteralPath $cardMaint)) {
                $links = @(cmd /c "fsutil hardlink list `"$card`"" 2>$null | Where-Object { $_.Trim() -ne '' })
                if ($links.Count -ge 2) {
                    Write-Host "  ok     onboarding card hardlink intact ($($links.Count) links)"
                } else {
                    $rootBytes = [System.IO.File]::ReadAllBytes($card)
                    $maintBytes = [System.IO.File]::ReadAllBytes($cardMaint)
                    $same = [System.Linq.Enumerable]::SequenceEqual($rootBytes, $maintBytes)
                    if ($FixHardlink) {
                        $src = if ((Get-Item -LiteralPath $card).LastWriteTimeUtc -ge (Get-Item -LiteralPath $cardMaint).LastWriteTimeUtc) { $card } else { $cardMaint }
                        $dst = if ($src -eq $card) { $cardMaint } else { $card }
                        Remove-Item -LiteralPath $dst -Force
                        cmd /c "mklink /H `"$dst`" `"$src`"" | Out-Null
                        if ($LASTEXITCODE -eq 0) {
                            Write-Host "  FIXED  rebuilt hardlink from newer copy ($src)" -ForegroundColor Yellow
                        } else {
                            Write-Host "  FAIL   could not rebuild hardlink between $card and $cardMaint" -ForegroundColor Red
                            $failures++
                        }
                    } elseif ($same) {
                        Write-Host "  WARN   hardlink broken (contents match; pass -FixHardlink to relink)" -ForegroundColor Yellow
                    } else {
                        Write-Host "  FAIL   hardlink broken AND contents differ between root and maintenance card" -ForegroundColor Red
                        $failures++
                    }
                }
            }
        }

        Write-Host ''
        if ($failures -gt 0) {
            Write-Host "CLOSEOUT CHECK FAILED ($failures issue(s))" -ForegroundColor Red
            exit 1
        } else {
            Write-Host 'ALL CLOSEOUT CHECKS PASSED' -ForegroundColor Green
        }
    }

    Write-Host ''
} finally {
    Pop-Location
}
