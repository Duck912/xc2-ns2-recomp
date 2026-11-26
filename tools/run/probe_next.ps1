# probe_next.ps1 -- one double-click = the next state of the "who draws the flat plate" sweep.
# The state stays until the next click; nothing blinks. State 0 is the baseline (everything on).
$dir = $PSScriptRoot
$stateFile = Join-Path $dir 'probe_state.txt'
$skipFile  = Join-Path $dir 'skip_uvdiv.txt'
$states = @(
    @{ n = 0;  hash = '';         text = '基线：全部开启' },
    @{ n = 1;  hash = '57bdd1a0'; text = '关 57bdd1a0（50 笔云片 / 背景云）' },
    @{ n = 2;  hash = 'a1bee995'; text = '关 a1bee995（天空 / 大气）' },
    @{ n = 3;  hash = 'cc3eac68'; text = '关 cc3eac68（雾合成 pass）' },
    @{ n = 4;  hash = '2649526f'; text = '关 2649526f（froxel 体积雾）' },
    @{ n = 5;  hash = '0f7e5657'; text = '关 0f7e5657（云层网格 9009 tri）' },
    @{ n = 6;  hash = '2bde5f34'; text = '关 2bde5f34' },
    @{ n = 7;  hash = '1cc22edc'; text = '关 1cc22edc' },
    @{ n = 8;  hash = 'cbb14c3a'; text = '关 cbb14c3a' },
    @{ n = 9;  hash = 'f9d7097a'; text = '关 f9d7097a' },
    @{ n = 10; hash = '66624ea6'; text = '关 66624ea6' },
    @{ n = 11; hash = '7712e1ca'; text = '关 7712e1ca' },
    @{ n = 12; hash = '7e09fd21'; text = '关 7e09fd21（22 笔 -> 雾体积 t297）' },
    @{ n = 13; hash = '8d9252cf'; text = '关 8d9252cf（24 笔 -> 雾体积 t297）' },
    @{ n = 14; hash = '49d94060'; text = '关 49d94060（2 笔 -> 雾体积 t297）' },
    @{ n = 15; hash = 'e1de556e'; text = '关 e1de556e（52 笔 -> 雾体积 t297，云团本体）' }
)
$cur = 0
if (Test-Path $stateFile) { $t = (Get-Content $stateFile -Raw).Trim(); if ($t -match '^\d+$') { $cur = [int]$t } }
$next = ($cur + 1) % $states.Count
$s = $states[$next]
if ($s.hash -eq '') { Set-Content -Path $skipFile -Value '' -NoNewline -Encoding ascii }
else { Set-Content -Path $skipFile -Value $s.hash -Encoding ascii }
Set-Content -Path $stateFile -Value $next
Write-Host ''
Write-Host ('  =====  STATE {0} / {1}  =====' -f $next, ($states.Count - 1)) -ForegroundColor Cyan
Write-Host ('  ' + $s.text) -ForegroundColor Yellow
Write-Host ''
if ($s.hash -ne '') { Write-Host ('  skip list: ' + $s.hash) } else { Write-Host '  skip list: (empty)' }
Write-Host ''
Write-Host '  双击本文件 = 下一个状态。'
Write-Host ''
