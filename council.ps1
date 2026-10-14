$ErrorActionPreference = 'Stop'
$runtimePython = Join-Path $PSScriptRoot 'runtime/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $runtimePython -PathType Leaf)) { throw 'Council runtime is missing. Run setup-council.ps1 first.' }
$previousCouncilRoot = $env:COUNCIL_ROOT
try {
    $env:COUNCIL_ROOT = $PSScriptRoot
    & $runtimePython -I -m council @args
    exit $LASTEXITCODE
} finally { $env:COUNCIL_ROOT = $previousCouncilRoot }
