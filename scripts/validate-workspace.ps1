<# Native Council integrity checks. No dependency on an author's workspace scripts. #>
[CmdletBinding()]
param([string]$WorkspaceRoot)
$ErrorActionPreference = 'Stop'
$CouncilRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$metadataPath = Join-Path $CouncilRoot 'installation.json'
if (-not (Test-Path -LiteralPath $metadataPath -PathType Leaf)) { throw 'Run this validator from the installed Council after setup.' }
$metadata = Get-Content -LiteralPath $metadataPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $WorkspaceRoot) { $WorkspaceRoot = $metadata.workspaceRoot }
$node = $metadata.nodePath
& $node (Join-Path $PSScriptRoot 'council-source.mjs') check $CouncilRoot
if ($LASTEXITCODE -ne 0) { throw 'Council source verification failed.' }
& $node (Join-Path $PSScriptRoot 'council-codex.mjs') validate --workspace $WorkspaceRoot --home $metadata.homeDir --payload $CouncilRoot
if ($LASTEXITCODE -ne 0) { throw 'Council static placement verification failed.' }
$psFiles = @((Join-Path $CouncilRoot 'setup-council.ps1')) + @(Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.ps1' -File -Recurse | Select-Object -ExpandProperty FullName)
foreach ($file in $psFiles) {
    $parserTokens = $null
    $parserErrors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($file, [ref]$parserTokens, [ref]$parserErrors)
    if ($parserErrors.Count) { throw "PowerShell syntax errors: $file" }
}
Write-Host 'Native source, placement and PowerShell syntax checks passed. Hook trust and live behavior remain separate.'
exit 0
