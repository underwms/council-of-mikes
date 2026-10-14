[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$CouncilRoot,
    [Parameter(Mandatory)][string]$WorkspaceRoot,
    [string]$PythonPath,
    [switch]$PrerequisitesOnly,
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'PowerShell 7 or later is required for engine provisioning.' }
$CouncilRoot = [IO.Path]::GetFullPath($CouncilRoot)
$WorkspaceRoot = (Resolve-Path -LiteralPath $WorkspaceRoot).Path
function Assert-LocalPath([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    if (-not $full.StartsWith($CouncilRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Runtime path escapes Council root.' }
    $current = $full
    while ($current -and $current.Length -ge $CouncilRoot.Length) {
        if (Test-Path -LiteralPath $current) {
            if ((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Runtime paths cannot traverse junctions or links.' }
        }
        $current = Split-Path -Parent $current
    }
}
function Invoke-Checked([string]$Executable, [string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Runtime command failed with exit code $LASTEXITCODE." }
}
if (-not $ValidateOnly) {
    if (-not $PythonPath) {
        foreach ($candidate in @('python', 'python3')) {
            $found = Get-Command $candidate -ErrorAction SilentlyContinue
            if ($found) { $PythonPath = $found.Source; break }
        }
    }
    if (-not $PythonPath) { throw 'Python 3.11 or later is required. Supply -PythonPath if it is not on PATH.' }
    $details = & $PythonPath -I -c "import json,sys; print(json.dumps({'executable':sys.executable,'version':list(sys.version_info[:3])}))"
    if ($LASTEXITCODE -ne 0) { throw 'Python prerequisite check failed.' }
    $pythonInfo = $details | ConvertFrom-Json
    if ($pythonInfo.version[0] -ne 3 -or $pythonInfo.version[1] -lt 11) { throw 'Python 3.11 or later is required.' }
    $PythonPath = $pythonInfo.executable
    if ($PrerequisitesOnly) { return }
}
$engineRoot = Join-Path $CouncilRoot 'council'
$runtimeRoot = Join-Path $CouncilRoot 'runtime'
Assert-LocalPath $engineRoot
Assert-LocalPath $runtimeRoot
$engineFiles = Get-ChildItem -LiteralPath $engineRoot -File -Recurse | Where-Object {
    $_.FullName -notmatch '[\\/](?:__pycache__|build|dist|[^\\/]+\.egg-info)[\\/]' -and $_.Extension -ne '.pyc'
} | Sort-Object FullName
foreach ($file in $engineFiles) { Assert-LocalPath $file.FullName }
$fingerprintText = ($engineFiles | ForEach-Object { $_.FullName.Substring($engineRoot.Length).TrimStart('\', '/').Replace('\','/') + ':' + (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }) -join "`n"
$hasher = [Security.Cryptography.SHA256]::Create()
try { $sourceHash = [BitConverter]::ToString($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($fingerprintText))).Replace('-', '') }
finally { $hasher.Dispose() }
$runtimePython = Join-Path $runtimeRoot 'Scripts/python.exe'
$markerPath = Join-Path $runtimeRoot 'council-runtime.json'
Assert-LocalPath $runtimePython
Assert-LocalPath $markerPath
$marker = $null
if (Test-Path -LiteralPath $markerPath) {
    try { $marker = Get-Content -LiteralPath $markerPath -Raw | ConvertFrom-Json }
    catch { if ($ValidateOnly) { throw 'Council runtime marker is invalid.' } }
}
$current = $marker -and $marker.sourceHash -eq $sourceHash -and (Test-Path -LiteralPath $runtimePython)
if ($current) {
    & $runtimePython -I -m pip check *> $null
    $current = $LASTEXITCODE -eq 0
    if ($current) {
        & $runtimePython -I -m council --doctor --workspace $WorkspaceRoot --council-root $CouncilRoot *> $null
        $current = $LASTEXITCODE -eq 0
    }
}
if ($ValidateOnly -and -not $current) { throw 'Council runtime is missing or stale. Run setup-council.ps1 to provision it.' }
if (-not $current) {
    $buildRoot = Join-Path $CouncilRoot ('work/engine-build-' + [guid]::NewGuid())
    Assert-LocalPath $buildRoot
    New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
    foreach ($file in $engineFiles) {
        Assert-LocalPath $file.FullName
        $destination = Join-Path $buildRoot ([IO.Path]::GetRelativePath($engineRoot, $file.FullName))
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $destination
    }
    try {
        Invoke-Checked $PythonPath @('-I','-m','venv',$runtimeRoot)
        Invoke-Checked $runtimePython @('-I','-m','pip','install','setuptools==84.0.0','wheel==0.48.0')
        $wheelRoot = Join-Path $buildRoot 'wheelhouse'
        Invoke-Checked $runtimePython @('-I','-m','pip','wheel','--no-deps','--no-build-isolation','--wheel-dir',$wheelRoot,$buildRoot)
        $wheels = @(Get-ChildItem -LiteralPath $wheelRoot -Filter '*.whl')
        if ($wheels.Count -ne 1) { throw 'Expected exactly one Council wheel.' }
        $wheel = $wheels[0]
        Invoke-Checked $runtimePython @('-I','-m','pip','install','--force-reinstall','--constraint',(Join-Path $engineRoot 'requirements.lock'),$wheel.FullName)
        Invoke-Checked $runtimePython @('-I','-m','pip','check')
        Invoke-Checked $runtimePython @('-I','-m','council','--doctor','--workspace',$WorkspaceRoot,'--council-root',$CouncilRoot)
        @{ sourceHash=$sourceHash; pythonVersion=$pythonInfo.version; packageVersion='0.2.0'; wheelHash=(Get-FileHash -LiteralPath $wheel.FullName -Algorithm SHA256).Hash } | ConvertTo-Json | Set-Content -LiteralPath $markerPath -Encoding utf8
    } finally {
        Assert-LocalPath $buildRoot
        if (Test-Path -LiteralPath $buildRoot) { Remove-Item -LiteralPath $buildRoot -Recurse -Force }
    }
}
Invoke-Checked $runtimePython @('-I','-m','pip','check')
Invoke-Checked $runtimePython @('-I','-m','council','--doctor','--workspace',$WorkspaceRoot,'--council-root',$CouncilRoot)
Write-Host 'Council Python runtime and offline engine doctor verified. No provider requests were made.'
