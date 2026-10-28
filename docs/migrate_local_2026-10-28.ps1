<#
.SYNOPSIS
  2026-10-28 仓库按人重构后，把本机被 Git 忽略、没跟着合并走的文件挪到新位置。

.DESCRIPTION
  合并 claude/trusting-brown-h7384r 之后运行。Git 只移动已跟踪的文件；被忽略的文件
  （建模运行时 3mf\.runtime、geometry/checks/views、BrailleModule_Video\Archives、
  agent 后端的 .env 和 node_modules、实验服务的 cert.pem/key.pem、data\ 等）还留在旧目录。

  规则：
  - 只移动，不删除，不覆盖。
  - 旧位置不存在 → 跳过。
  - 新位置已有同名文件 → 跳过，两边都保留，最后列出来由你处理。
  - 新位置已有同名目录 → 进入目录逐项合并。
  - 每一步都打印。
  最后在 hardware\models\ 下用 mklink /J 建目录联接 .pcba-workflow，指向仓库根目录的
  .pcba-workflow（根目录那份不动）。hardware\models\3mf\Handle_NewPCB_2026-10-20\build.py
  和 measure_sources.py 用 parents[1] 找它，移动后会在 hardware\models\ 下找。

.PARAMETER DryRun
  只打印将要做什么，不实际移动、不建联接。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File docs\migrate_local_2026-10-28.ps1 -DryRun
  powershell -ExecutionPolicy Bypass -File docs\migrate_local_2026-10-28.ps1
#>
param([switch]$DryRun)

$ErrorActionPreference = 'Stop'

function Find-RepoRoot {
    try {
        $top = (& git -C $PSScriptRoot rev-parse --show-toplevel 2>$null)
        if ($LASTEXITCODE -eq 0 -and $top) { return (Resolve-Path -LiteralPath $top).Path }
    } catch { }
    # 没有 git 时退回到本脚本所在目录（<仓库根>\docs）的上一级
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
}

$Root = Find-RepoRoot
$script:Failures = @()
$script:Conflicts = @()

function Get-Rel([string]$Path) {
    if ($Path.StartsWith($Root, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $Path.Substring($Root.Length).TrimStart('\', '/')
    }
    return $Path
}

function Write-Step([string]$Action, [string]$Text) {
    $prefix = if ($DryRun) { '[演练] ' } else { '' }
    Write-Host ("{0}{1}：{2}" -f $prefix, $Action, $Text)
}

function Ensure-Parent([string]$Path) {
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) {
        Write-Step '建目录' (Get-Rel $parent)
        if (-not $DryRun) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    }
}

function Merge-Dir([string]$Src, [string]$Dst) {
    foreach ($item in @(Get-ChildItem -LiteralPath $Src -Force)) {
        $target = Join-Path $Dst $item.Name
        if (-not (Test-Path -LiteralPath $target)) {
            Write-Step '移动' ("{0} -> {1}" -f (Get-Rel $item.FullName), (Get-Rel $target))
            if (-not $DryRun) {
                try {
                    Ensure-Parent $target
                    Move-Item -LiteralPath $item.FullName -Destination $target
                } catch {
                    $script:Failures += ("{0}：{1}" -f (Get-Rel $item.FullName), $_.Exception.Message)
                    Write-Step '失败' ("{0}：{1}" -f (Get-Rel $item.FullName), $_.Exception.Message)
                }
            }
        } elseif ($item.PSIsContainer -and (Get-Item -LiteralPath $target -Force).PSIsContainer) {
            Merge-Dir $item.FullName $target
        } else {
            $script:Conflicts += (Get-Rel $item.FullName)
            Write-Step '跳过' ("新位置已有同名项，未覆盖：{0}（旧的留在 {1}）" -f (Get-Rel $target), (Get-Rel $item.FullName))
        }
    }
}

Write-Host "仓库根目录：$Root"
if ($DryRun) { Write-Host '演练模式：只打印，不移动。' }

if (-not (Test-Path -LiteralPath (Join-Path $Root 'hardware\models\3mf\README.md'))) {
    Write-Host '没找到 hardware\models\3mf\README.md：新布局还不在工作区里。请先合并 claude/trusting-brown-h7384r 再运行。'
    exit 1
}

# 旧位置 -> 新位置（与 2026-10-28 的 git mv 一致）
$Moves = @(
    @('3mf', 'hardware\models\3mf'),
    @('BrailleModule', 'hardware\models\BrailleModule'),
    @('BrailleModule_Video', 'hardware\models\BrailleModule_Video'),
    @('PCB_REDESIGN_2026-10-08', 'hardware\pcb\PCB_REDESIGN_2026-10-08'),
    @('firmware', 'hardware\firmware'),
    @('visionss', 'experiments\chi2027\visionss'),
    @('single_point', 'experiments\chi2027\single_point'),
    @('vision', 'archive\vision'),
    @('app\frontend', 'archive\app\frontend'),
    @('app\backend', 'agent\backend'),
    @('handoff_2026-10-28\cs30_protocol', 'perception\cs30'),
    @('handoff_2026-10-28\plans', 'docs\plans')
)

foreach ($m in $Moves) {
    $src = Join-Path $Root $m[0]
    $dst = Join-Path $Root $m[1]
    if (-not (Test-Path -LiteralPath $src)) {
        Write-Step '跳过' ("{0} 不存在" -f $m[0])
        continue
    }
    Write-Host ("--- {0} -> {1}" -f $m[0], $m[1])
    Merge-Dir $src $dst
}

Write-Host '--- .pcba-workflow 目录联接'
$link = Join-Path $Root 'hardware\models\.pcba-workflow'
$linkTarget = Join-Path $Root '.pcba-workflow'
if (-not (Test-Path -LiteralPath $linkTarget)) {
    Write-Step '跳过' '仓库根目录没有 .pcba-workflow'
} elseif (Test-Path -LiteralPath $link) {
    Write-Step '跳过' 'hardware\models\.pcba-workflow 已存在'
} else {
    Write-Step '建联接' ("mklink /J `"{0}`" `"{1}`"" -f $link, $linkTarget)
    if (-not $DryRun) {
        try {
            $out = & cmd /c mklink /J "$link" "$linkTarget" 2>&1
            Write-Host $out
            if ($LASTEXITCODE -ne 0) { $script:Failures += "mklink /J：$out" }
        } catch {
            $script:Failures += ("mklink /J：{0}" -f $_.Exception.Message)
            Write-Step '失败' ("mklink /J：{0}" -f $_.Exception.Message)
        }
    }
}

Write-Host '--- 旧目录现状（脚本不删除任何目录）'
foreach ($old in @('3mf', 'BrailleModule', 'BrailleModule_Video', 'PCB_REDESIGN_2026-10-08', 'firmware',
                   'visionss', 'single_point', 'vision', 'app', 'handoff_2026-10-28')) {
    $p = Join-Path $Root $old
    if (-not (Test-Path -LiteralPath $p)) { continue }
    $left = @(Get-ChildItem -LiteralPath $p -Recurse -Force -File -ErrorAction SilentlyContinue)
    if ($left.Count -eq 0) {
        Write-Host ("{0}\ 里已经没有文件，可以手动删除（只剩空目录）" -f $old)
    } else {
        Write-Host ("{0}\ 里还有 {1} 个文件没挪走，见上面的「跳过」「失败」" -f $old, $left.Count)
    }
}

if ($script:Conflicts.Count -gt 0) {
    Write-Host '--- 新位置已有同名项、没有覆盖的：'
    $script:Conflicts | ForEach-Object { Write-Host "  $_" }
}
if ($script:Failures.Count -gt 0) {
    Write-Host '--- 失败的：'
    $script:Failures | ForEach-Object { Write-Host "  $_" }
}

Write-Host '--- 提醒'
Write-Host '建模命令改在 hardware\models\ 下执行（那里相当于原来的仓库根），例如：'
Write-Host '  cd hardware\models; .\3mf\.runtime\structural-runtime\Scripts\python.exe -B 3mf\regenerate.py --require-baseline'
Write-Host '.runtime 里的启动脚本（pip.exe 等）可能还记着旧路径，按 3mf\README.md 直接用 python.exe / python -m pip。'
Write-Host '如果实验服务的 cert.pem/key.pem 没有挪过去，首次运行会生成新证书，手机要重新接受一次。'
Write-Host 'agent\backend 没有 node_modules 时，在该目录运行 npm ci。'
if ($DryRun) { Write-Host '演练结束，什么都没改。去掉 -DryRun 再运行一次即可执行。' }
