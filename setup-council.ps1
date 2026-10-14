[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$WorkspaceRoot,
    [string]$HomeRoot = $env:USERPROFILE,
    [string]$NodePath,
    [string]$PythonPath,
    [switch]$ValidateOnly,
    [switch]$SkipGeminiOptimization,
    [switch]$NativeOnly
)
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 5 -or ($PSVersionTable.PSVersion.Major -eq 5 -and $PSVersionTable.PSVersion.Minor -lt 1)) { throw 'PowerShell 5.1 or later is required.' }
if (-not $NativeOnly -and $PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7+ is required for the Python engine. Use -NativeOnly for client setup on PowerShell 5.1.' }
$WorkspaceRoot = (Resolve-Path -LiteralPath $WorkspaceRoot).Path
if (-not (Test-Path -LiteralPath $WorkspaceRoot -PathType Container)) { throw 'WorkspaceRoot must be a directory.' }
$HomeRoot = [IO.Path]::GetFullPath($HomeRoot)
if (-not $NodePath) { $NodePath = (Get-Command node -ErrorAction Stop).Source }
$NodePath = (Resolve-Path -LiteralPath $NodePath).Path
$nodeVersion = & $NodePath --version
if ($LASTEXITCODE -ne 0 -or [int]($nodeVersion.TrimStart('v').Split('.')[0]) -lt 20) { throw 'Node.js 20 or later is required.' }
$CouncilRoot = Join-Path $HomeRoot '.council'
$workspacePrefix = $WorkspaceRoot.TrimEnd('\') + '\'
if ($CouncilRoot.StartsWith($workspacePrefix, [StringComparison]::OrdinalIgnoreCase) -or $WorkspaceRoot.StartsWith($CouncilRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase) -or $WorkspaceRoot -eq $CouncilRoot) { throw 'WorkspaceRoot must be separate from Council and profile roots.' }
foreach ($name in @('.codex','.gemini','.claude','.agents','.aws')) {
    $privateRoot = Join-Path $HomeRoot $name
    if ($WorkspaceRoot -eq $privateRoot -or $WorkspaceRoot.StartsWith($privateRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or $privateRoot.StartsWith($workspacePrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'WorkspaceRoot overlaps a private client directory.' }
}
$SourceRoot = if ($ValidateOnly) { $CouncilRoot } else { $PSScriptRoot }
& $NodePath (Join-Path $SourceRoot 'scripts/council-source.mjs') check $SourceRoot
if ($LASTEXITCODE -ne 0) { throw 'Council source verification failed.' }
if (-not $ValidateOnly -and -not $NativeOnly) {
    & (Join-Path $SourceRoot 'scripts/install-engine-runtime.ps1') -CouncilRoot $CouncilRoot -WorkspaceRoot $WorkspaceRoot -PythonPath $PythonPath -PrerequisitesOnly
}
$command = if ($ValidateOnly) { 'validate' } else { 'install' }
& $NodePath (Join-Path $SourceRoot 'scripts/council-codex.mjs') $command --workspace $WorkspaceRoot --home $HomeRoot --payload $SourceRoot --node $NodePath
if ($LASTEXITCODE -ne 0) { throw 'Council static installation verification failed.' }
if (-not $ValidateOnly -and -not $SkipGeminiOptimization) {
    $optimizerScript = Join-Path $CouncilRoot 'scripts/optimize-gemini-cli.ps1'
    if (Test-Path -LiteralPath $optimizerScript -PathType Leaf) {
        & $optimizerScript -NodePath $NodePath
    }
}
if (-not $NativeOnly) {
    & (Join-Path $CouncilRoot 'scripts/install-engine-runtime.ps1') -CouncilRoot $CouncilRoot -WorkspaceRoot $WorkspaceRoot -PythonPath $PythonPath -ValidateOnly:$ValidateOnly
}
& $NodePath (Join-Path $CouncilRoot 'scripts/council-source.mjs') check $CouncilRoot
if ($LASTEXITCODE -ne 0) { throw 'Installed source verification failed.' }
if ($NativeOnly) { Write-Host 'Council source and static client placement verified. Python engine provisioning skipped.' }
else { Write-Host 'Council source, static placement, and offline engine verified.' }
Write-Host 'Review and trust native hooks in each client; verify fresh native startup separately.'
