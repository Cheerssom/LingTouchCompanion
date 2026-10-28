param(
    [Parameter(Mandatory = $true, Position = 0)] [string] $Json,
    [string] $Out,
    [switch] $Validate
)
$ErrorActionPreference = 'Stop'
$taskRuntime = Join-Path $PSScriptRoot '..\..\3mf\.runtime\structural-runtime\Scripts\python.exe'
$taskScript = Join-Path $PSScriptRoot 'generate_video.py'
if (-not (Test-Path -LiteralPath $taskRuntime)) { throw "Missing retained Blender Python: $taskRuntime" }
$taskArgs = @('-B', $taskScript, (Resolve-Path -LiteralPath $Json).Path)
if ($Out) { $taskArgs += @('--out', $Out) }
if ($Validate) { $taskArgs += '--validate' }
& $taskRuntime @taskArgs
if ($LASTEXITCODE -ne 0) { throw "Video generation failed (exit $LASTEXITCODE). See the message above." }
