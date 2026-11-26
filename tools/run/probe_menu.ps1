# probe_menu.ps1 -- pick a state by number instead of stepping through them.
# The state stays until you pick another one; the game keeps running.
$dir = $PSScriptRoot
$stateFile = Join-Path $dir 'probe_state.txt'
$skipFile  = Join-Path $dir 'skip_uvdiv.txt'
$states = @(
    @{ hash = '';         text = '基线：全部开启' },
    @{ hash = '57bdd1a0'; text = '50 笔云片 / 背景云' },
    @{ hash = 'a1bee995'; text = '天空 / 大气' },
    @{ hash = 'cc3eac68'; text = '雾合成 pass' },
    @{ hash = '2649526f'; text = 'froxel 体积雾' },
    @{ hash = '0f7e5657'; text = '云层网格 (9009 tri)' },
    @{ hash = '2bde5f34'; text = '(世界 forward pass)' },
    @{ hash = '1cc22edc'; text = '(t13 forward pass)' },
    @{ hash = 'cbb14c3a'; text = '(t13 forward pass)' },
    @{ hash = 'f9d7097a'; text = '(t13 forward pass)' },
    @{ hash = '66624ea6'; text = '(t13 forward pass)' },
    @{ hash = '7712e1ca'; text = '(t13 forward pass)' },
    @{ hash = '7e09fd21'; text = '22 笔 -> 雾体积 t297' },
    @{ hash = '8d9252cf'; text = '24 笔 -> 雾体积 t297' },
    @{ hash = '49d94060'; text = '2 笔 -> 雾体积 t297' },
    @{ hash = 'e1de556e'; text = '52 笔 -> 雾体积 t297（云团本体）' }
)
function Apply([int]$i) {
    $s = $states[$i]
    if ($s.hash -eq '') { Set-Content -Path $skipFile -Value '' -NoNewline -Encoding ascii }
    else { Set-Content -Path $skipFile -Value $s.hash -Encoding ascii }
    Set-Content -Path $stateFile -Value $i
}
$cur = 0
if (Test-Path $stateFile) { $t = (Get-Content $stateFile -Raw).Trim(); if ($t -match '^\d+$') { $cur = [int]$t } }

while ($true) {
    Clear-Host
    Write-Host ''
    Write-Host '  ============================================================' -ForegroundColor DarkCyan
    Write-Host '   雾/平片 状态选择器  （输入编号回车生效；q 退出）' -ForegroundColor Cyan
    Write-Host '  ============================================================' -ForegroundColor DarkCyan
    for ($i = 0; $i -lt $states.Count; $i++) {
        $mark = if ($i -eq $cur) { '> ' } else { '  ' }
        $col = if ($i -eq $cur) { 'Green' } else { 'Gray' }
        $hash = if ($states[$i].hash -eq '') { '(无)' } else { $states[$i].hash }
        Write-Host ('{0}{1,2}  {2,-9} {3}' -f $mark, $i, $hash, $states[$i].text) -ForegroundColor $col
    }
    Write-Host ''
    $skText = Get-Content -Path $skipFile -Raw -ErrorAction SilentlyContinue
    if ($null -eq $skText) { $skText = '' } else { $skText = $skText.Trim() }
    if ($skText -eq '') { $skText = '（空 = 全部开启）' }
    Write-Host ('  当前：STATE {0}   skip 文件内容 = [{1}]' -f $cur, $skText) -ForegroundColor Yellow
    Write-Host ''
    $in = Read-Host '  编号'
    if ($in -eq 'q' -or $in -eq 'Q') { break }
    if ($in -match '^\d+$') {
        $n = [int]$in
        if ($n -ge 0 -and $n -lt $states.Count) { $cur = $n; Apply $n }
    }
    $in = $null
}
