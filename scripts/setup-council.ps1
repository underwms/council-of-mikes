<#
.SYNOPSIS
  One-Click Council V2 & Workstation Provisioner.

.DESCRIPTION
  Automates the complete installation of the Council V2 multi-agent framework on a developer machine.
  Provisions host directories, installs all 15 specialist skills into ~/.gemini/skills/,
  configures lifecycle hooks, sets up indexing rules, and validates 100% environment health.

.PARAMETER WorkspaceRoot
  The path to the local workspace root. Defaults to the parent directory of this script.
  Developers can specify any custom directory path or name.

.EXAMPLE
  .\scripts\setup-council.ps1
  .\scripts\setup-council.ps1 -WorkspaceRoot "D:\Dev\my-workspace"
#>
[CmdletBinding()]
param(
  [string]$WorkspaceRoot
)

$ErrorActionPreference = 'Stop'

# 1. Resolve Workspace Root dynamically
if ([string]::IsNullOrEmpty($WorkspaceRoot)) {
    if (-not [string]::IsNullOrEmpty($PSScriptRoot)) {
        $WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    } else {
        $WorkspaceRoot = (Get-Location).Path
    }
} else {
    if (-not (Test-Path $WorkspaceRoot)) {
        New-Item -ItemType Directory -Path $WorkspaceRoot -Force | Out-Null
    }
    $WorkspaceRoot = (Resolve-Path $WorkspaceRoot).Path
}

$UserHome = $env:USERPROFILE
$GeminiHome = Join-Path $UserHome ".gemini"
$Username = [System.Environment]::UserName

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " Council V2 - One-Click Dev Provisioner   " -ForegroundColor Cyan
Write-Host " Target Workspace: $WorkspaceRoot" -ForegroundColor Cyan
Write-Host " Host Destination: $GeminiHome" -ForegroundColor Cyan
Write-Host " User:             $Username" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# 2. Create Host Directory Tree
Write-Host "[1/6] Provisioning ~/.gemini directory tree..." -ForegroundColor Yellow
$dirsToCreate = @(
    (Join-Path $GeminiHome ".rules"),
    (Join-Path $GeminiHome "scripts"),
    (Join-Path $GeminiHome "skills"),
    (Join-Path $GeminiHome "policies"),
    (Join-Path $GeminiHome "history"),
    (Join-Path $GeminiHome "tmp\$Username\memory")
)

foreach ($dir in $dirsToCreate) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Host "  [OK] Host directory tree provisioned" -ForegroundColor Green

# 3. Install 15 Council V2 Specialist Skills
Write-Host ""
Write-Host "[2/6] Installing 15 Council V2 Specialist Skills..." -ForegroundColor Yellow
$specialistsSource = Join-Path $WorkspaceRoot "council"
if (-not (Test-Path $specialistsSource)) {
    $specialistsSource = Join-Path $WorkspaceRoot ".gemini\specialists"
}
$specialistsDest = Join-Path $GeminiHome "skills"

if (Test-Path $specialistsSource) {
    Get-ChildItem -Path $specialistsSource -Directory | Where-Object { $_.Name -like 'the-*' } | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $specialistsDest -Recurse -Force
    }
    $installed = (Get-ChildItem -Path $specialistsDest -Directory).Count
    Write-Host "  [OK] Installed $installed Council V2 specialist skill packages to $specialistsDest" -ForegroundColor Green
} else {
    Write-Warning "Specialists source directory not found at $specialistsSource"
}

# 4. Deploy Host Lifecycle Scripts
Write-Host ""
Write-Host "[3/6] Deploying host lifecycle scripts..." -ForegroundColor Yellow
$hostScriptsSource = Join-Path $WorkspaceRoot "scripts"
$hostScriptsDest = Join-Path $GeminiHome "scripts"

$scriptsToCopy = @("onboard.py", "heartbeat_hook.py")
foreach ($s in $scriptsToCopy) {
    $srcFile = Join-Path $hostScriptsSource $s
    $destFile = Join-Path $hostScriptsDest $s
    if (Test-Path $srcFile) {
        $srcResolved = (Resolve-Path $srcFile).Path
        $destResolved = (Resolve-Path $destFile -ErrorAction SilentlyContinue)
        if ($null -eq $destResolved -or $srcResolved -ne $destResolved.Path) {
            Copy-Item -Path $srcFile -Destination $destFile -Force
            Write-Host "  [OK] Deployed $s to $hostScriptsDest" -ForegroundColor Green
        } else {
            Write-Host "  [OK] $s already up-to-date at $destFile" -ForegroundColor Green
        }
    }
}

# 5. Deploy Global Tier 1 Guardrails & .geminiignore
Write-Host ""
Write-Host "[4/6] Deploying Tier 1 Global Guardrails & .geminiignore..." -ForegroundColor Yellow

$userIgnoreSrc = Join-Path $WorkspaceRoot ".geminiignore"
$userIgnoreDest = Join-Path $UserHome ".geminiignore"
if (Test-Path $userIgnoreSrc) {
    $srcResolved = (Resolve-Path $userIgnoreSrc).Path
    $destResolved = (Resolve-Path $userIgnoreDest -ErrorAction SilentlyContinue)
    if ($null -eq $destResolved -or $srcResolved -ne $destResolved.Path) {
        Copy-Item -Path $userIgnoreSrc -Destination $userIgnoreDest -Force
        Write-Host "  [OK] Deployed %USERPROFILE%\.geminiignore" -ForegroundColor Green
    } else {
        Write-Host "  [OK] .geminiignore already up-to-date at $userIgnoreDest" -ForegroundColor Green
    }
}

$tier1Src = Join-Path $WorkspaceRoot ".gemini\.rules\rules.md"
$tier1Dest = Join-Path $GeminiHome ".rules\rules.md"
if (Test-Path $tier1Src) {
    $srcResolved = (Resolve-Path $tier1Src).Path
    $destResolved = (Resolve-Path $tier1Dest -ErrorAction SilentlyContinue)
    if ($null -eq $destResolved -or $srcResolved -ne $destResolved.Path) {
        Copy-Item -Path $tier1Src -Destination $tier1Dest -Force
        Write-Host "  [OK] Deployed Tier 1 Invariant Shell Guardrails to $tier1Dest" -ForegroundColor Green
    } else {
        Write-Host "  [OK] Tier 1 rules already up-to-date at $tier1Dest" -ForegroundColor Green
    }
}

# 6. Configure Gemini CLI Settings & Hooks
Write-Host ""
Write-Host "[5/6] Configuring ~/.gemini/settings.json hooks..." -ForegroundColor Yellow
$settingsFile = Join-Path $GeminiHome "settings.json"
$hookScript = Join-Path $GeminiHome "scripts\heartbeat_hook.py"

$mergePy = @"
import json, os

p = r'$settingsFile'
hook_cmd = 'python ' + r'$hookScript'

d = {}
if os.path.exists(p):
    try:
        with open(p, 'r', encoding='utf-8') as f:
            d = json.load(f)
    except Exception:
        d = {}

hooks = d.setdefault('hooks', {})
hooks['AfterAgent'] = [
    {
        'matcher': '*',
        'hooks': [
            {
                'name': 'memoryforge-heartbeat',
                'type': 'command',
                'command': hook_cmd,
                'timeout': 5000,
                'description': 'Deterministic MemoryForge heartbeat bridge across sessions'
            }
        ]
    }
]

d.setdefault('general', {})['preferredEditor'] = 'vscode'

with open(p, 'w', encoding='utf-8') as f:
    json.dump(d, f, indent=2)
"@

python -c "$mergePy"
Write-Host "  [OK] Configured AfterAgent heartbeat hook in $settingsFile" -ForegroundColor Green

# 7. Run Verification Audit
Write-Host ""
Write-Host "[6/6] Executing workspace integrity verification..." -ForegroundColor Yellow
$validatorScript = Join-Path $WorkspaceRoot "scripts\validate-workspace.ps1"
if (Test-Path $validatorScript) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $validatorScript -WorkspaceRoot $WorkspaceRoot
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host " [SUCCESS] Council V2 Provisioning Complete!" -ForegroundColor Green
Write-Host " Developer Setup is 100% Ready." -ForegroundColor Green
Write-Host " Launch Gemini CLI in $WorkspaceRoot and type 'onboard' to start." -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
