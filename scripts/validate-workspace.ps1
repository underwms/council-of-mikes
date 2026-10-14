<# Run the existing workspace validator against canonical Council definitions. Read-only. #>
[CmdletBinding()]
param([string]$WorkspaceRoot)
$ErrorActionPreference = 'Stop'
$CouncilRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $WorkspaceRoot) {
    $installation = Get-Content -LiteralPath (Join-Path $CouncilRoot 'installation.json') -Raw | ConvertFrom-Json
    $WorkspaceRoot = $installation.workspaceRoot
}
$validator = Join-Path $WorkspaceRoot 'scripts\validate-workspace.ps1'
if (-not (Test-Path -LiteralPath $validator -PathType Leaf)) {
    throw "Configured workspace validator is missing: $validator"
}
& $validator -WorkspaceRoot $WorkspaceRoot -GlobalGeminiRoot $CouncilRoot
exit $LASTEXITCODE
