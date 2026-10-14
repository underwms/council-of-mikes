<# Version-specific Gemini CLI repair. Unknown versions remain untouched. #>
[CmdletBinding()]
param(
    [string]$GeminiNpmPath,
    [string]$NodePath,
    [switch]$Rollback,
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
if (-not $GeminiNpmPath) {
    $GeminiNpmPath = Join-Path $env:APPDATA 'npm\node_modules\@google\gemini-cli'
    if (-not (Test-Path -LiteralPath $GeminiNpmPath -PathType Container)) {
        $geminiCommand = Get-Command gemini -ErrorAction SilentlyContinue
        if ($geminiCommand) {
            $GeminiNpmPath = Join-Path (Split-Path -Parent $geminiCommand.Source) 'node_modules\@google\gemini-cli'
        }
    }
}
if (-not (Test-Path -LiteralPath $GeminiNpmPath -PathType Container)) {
    Write-Host 'Gemini CLI package not detected; compatibility repair skipped.'
    return
}
if (-not $NodePath) { $NodePath = (Get-Command node -ErrorAction Stop).Source }
$arguments = @((Join-Path $PSScriptRoot 'gemini-compat.mjs'), $GeminiNpmPath)
if ($Rollback) { $arguments += '--rollback' }
if ($ValidateOnly) { $arguments += '--validate-only' }
& $NodePath @arguments
if ($LASTEXITCODE -ne 0) { throw 'Gemini compatibility validation or repair failed; package changes were not certified.' }
