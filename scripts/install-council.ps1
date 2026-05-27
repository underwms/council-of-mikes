#Requires -Version 7.0
<#
.SYNOPSIS
  Install script for the Council of Mikes.
.DESCRIPTION
  Finds the nearest .claude/skills directory by locating 'accessibility-reviewer.md' (or falling back to standard search paths) and copies/links the Council skills.
#>
[CmdletBinding()]
param(
  [string]$DestinationPath,
  [switch]$Symlink
)

$ErrorActionPreference = 'Stop'
$scriptRoot = $PSScriptRoot
$repoRoot = (Resolve-Path (Join-Path $scriptRoot '..')).Path

Write-Host "Council of Mikes Installer" -ForegroundColor White
Write-Host "==========================" -ForegroundColor DarkGray

# Step 1: Resolve the target .claude/skills directory
$targetSkillsDir = $null

if ($DestinationPath) {
  if (Test-Path $DestinationPath) {
    $targetSkillsDir = $DestinationPath
  }
} else {
  # Search for the nearest accessibility-reviewer.md
  Write-Host "Searching for accessibility-reviewer.md to locate active workspace..." -ForegroundColor Gray

  # Build a dynamic list of search paths by going up parent hierarchy to avoid hardcoded user profile paths
  $searchPaths = [System.Collections.Generic.List[string]]::new()
  $searchPaths.Add($repoRoot)

  $current = $repoRoot
  for ($i = 0; $i -lt 3; $i++) {
    $current = Split-Path $current -Parent
    if ([string]::IsNullOrWhiteSpace($current)) { break }
    if ($searchPaths -notcontains $current) { $searchPaths.Add($current) }

    # Check all immediate children of this parent level
    $children = @()
    try {
      $children = Get-ChildItem -Path $current -Directory -ErrorAction SilentlyContinue
    } catch {}
    foreach ($c in $children) {
      if ($searchPaths -notcontains $c.FullName) {
        $searchPaths.Add($c.FullName)
      }
    }
  }

  foreach ($path in $searchPaths) {
    if (-not (Test-Path $path)) { continue }
    $found = Get-ChildItem -Path $path -Filter "accessibility-reviewer.md" -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) {
      # accessibility-reviewer.md is inside a skills folder, e.g. <workspace-root>/.claude/skills/... or <sub-repo>/.claude/skills/...
      # We want to find the .claude/skills directory
      $dir = $found.Directory
      while ($dir -ne $null -and $dir.Name -ne 'skills') {
        $dir = $dir.Parent
      }
      if ($dir -and $dir.Name -eq 'skills') {
        $targetSkillsDir = $dir.FullName
        Write-Host "Found target skills directory: $targetSkillsDir" -ForegroundColor Green
        break
      }
    }
  }
}

if (-not $targetSkillsDir) {
  # Fallback to current directory's .claude/skills or sibling
  Write-Host "Could not find accessibility-reviewer.md automatically." -ForegroundColor Yellow
  $defaultPath = Join-Path $repoRoot ".claude/skills"
  $resp = Read-Host "Enter destination path for .claude/skills (Default: $defaultPath)"
  if ([string]::IsNullOrWhiteSpace($resp)) {
    $targetSkillsDir = $defaultPath
  } else {
    $targetSkillsDir = $resp
  }
}

# Ensure destination exists
if (-not (Test-Path $targetSkillsDir)) {
  New-Item -ItemType Directory -Path $targetSkillsDir -Force | Out-Null
}

$councilDest = Join-Path $targetSkillsDir "council"
if (-not (Test-Path $councilDest)) {
  New-Item -ItemType Directory -Path $councilDest -Force | Out-Null
}

# Copy or link Council members
Write-Host "Installing Council members to $councilDest..." -ForegroundColor Cyan
$sourceCouncil = Join-Path $repoRoot "council"
if (Test-Path $sourceCouncil) {
  Get-ChildItem -Path $sourceCouncil -Directory | ForEach-Object {
    $dest = Join-Path $councilDest $_.Name
    if (Test-Path $dest) {
      Remove-Item -Recurse -Force $dest
    }
    if ($Symlink) {
      New-Item -ItemType Junction -Path $dest -Value $_.FullName | Out-Null
      Write-Host "  Junction created: $($_.Name)" -ForegroundColor Gray
    } else {
      Copy-Item -Path $_.FullName -Destination $dest -Recurse -Force
      Write-Host "  Copied: $($_.Name)" -ForegroundColor Gray
    }
  }
}

# Copy optional files (council.md)
$sourceCouncilMd = Join-Path $sourceCouncil "council.md"
if (Test-Path $sourceCouncilMd) {
  Copy-Item -Path $sourceCouncilMd -Destination $councilDest -Force
  Write-Host "  Copied: council.md" -ForegroundColor Gray
}

# Copy companion skills
Write-Host "Installing companion skills to $targetSkillsDir..." -ForegroundColor Cyan
$sourceSkills = Join-Path $repoRoot "skills"
if (Test-Path $sourceSkills) {
  Get-ChildItem -Path $sourceSkills -Directory | ForEach-Object {
    $dest = Join-Path $targetSkillsDir $_.Name
    if (Test-Path $dest) {
      Remove-Item -Recurse -Force $dest
    }
    if ($Symlink) {
      New-Item -ItemType Junction -Path $dest -Value $_.FullName | Out-Null
      Write-Host "  Junction created: $($_.Name)" -ForegroundColor Gray
    } else {
      Copy-Item -Path $_.FullName -Destination $dest -Recurse -Force
      Write-Host "  Copied: $($_.Name)" -ForegroundColor Gray
    }
  }
}

# Copy SOP/procedures
$proceduresDest = Join-Path (Split-Path $targetSkillsDir -Parent) "procedures"
if (-not (Test-Path $proceduresDest)) {
  New-Item -ItemType Directory -Path $proceduresDest -Force | Out-Null
}
$sourceProcedures = Join-Path $repoRoot "procedures"
if (Test-Path $sourceProcedures) {
  Write-Host "Installing procedures to $proceduresDest..." -ForegroundColor Cyan
  Copy-Item -Path $sourceProcedures\* -Destination $proceduresDest -Recurse -Force
  Write-Host "  Installed procedures." -ForegroundColor Gray
}

Write-Host "Installation successful." -ForegroundColor Green
