#Requires -Version 7.0
<#
.SYNOPSIS
  Install script for the Council of Mikes (with optional rebranding for domain-specific councils).

.DESCRIPTION
  Installs the Council members, companion skills, and procedures into a target workspace.

  Auto-discovers the target `.claude/skills` directory by searching for a known Superpowers
  skill marker (`accessibility-reviewer.md`) up to three parent levels above the script,
  or accepts an explicit `-DestinationPath`.

  Optionally rebrands the Council on install via `-CouncilName` (changes the skills subfolder
  name) and `-MemberMap` (renames individual member directories, e.g. `the-gatekeeper` ->
  `gatekeeper`). Use `-RewriteReferences` to also rewrite cross-references inside copied
  SKILL.md files to match the new names.

  Procedures install to `<workspace-root>/docs/procedures/` by default (matching the
  deployed convention) — override with `-ProceduresPath`.

.PARAMETER DestinationPath
  Explicit path to the `.claude/skills` directory of the target workspace.
  If omitted, the script auto-discovers it.

.PARAMETER CouncilName
  Display name of the council (e.g., "Order Processing Council"). Used to derive the
  skills subfolder slug (e.g., `order-processing-council`) and, when `-RewriteReferences`
  is set, used to substitute "The Council" in copied content.
  Defaults to "Council" (slug: `council`).

.PARAMETER MemberMap
  Path to a JSON file mapping generic member directory names to branded names, e.g.:
    { "the-gatekeeper": "gatekeeper", "the-architect": "solutions-architect" }
  Members not listed in the map are copied with their original directory names.

.PARAMETER ProceduresPath
  Destination directory for procedures/*.md. Defaults to `<workspace-root>/docs/procedures/`,
  where `<workspace-root>` is the parent of the `.claude` directory.

.PARAMETER RewriteReferences
  After copy, rewrite cross-references inside installed SKILL.md files:
    - member dir names (per -MemberMap)
    - "The Council" -> "<CouncilName>"
  Conservative best-effort; review the install with git diff after running.

.PARAMETER Backup
  Before clobbering an existing council folder or member directory, copy it to
  `<target>.backup-<yyyyMMddHHmmss>`.

.PARAMETER Symlink
  Use directory junctions (Windows) instead of copies. Junctions skip rebranding,
  rewriting, and backup — they always reflect the source repo as-is.

.EXAMPLE
  # Vanilla install into auto-discovered .claude/skills
  ./install-council.ps1

.EXAMPLE
  # Rebrand as "Order Processing Council" with member rename map
  ./install-council.ps1 -CouncilName "Order Processing Council" -MemberMap ./op-member-map.json -RewriteReferences -Backup
#>
[CmdletBinding()]
param(
  [string]$DestinationPath,
  [string]$CouncilName = 'Council',
  [string]$MemberMap,
  [string]$ProceduresPath,
  [switch]$RewriteReferences,
  [switch]$Backup,
  [switch]$Symlink
)

$ErrorActionPreference = 'Stop'
$scriptRoot = $PSScriptRoot
$repoRoot = (Resolve-Path (Join-Path $scriptRoot '..')).Path

function ConvertTo-Slug {
  param([string]$name)
  $s = $name.ToLowerInvariant().Trim()
  $s = ($s -replace '[^a-z0-9]+', '-').Trim('-')
  if ([string]::IsNullOrWhiteSpace($s)) { return 'council' }
  return $s
}

function Backup-IfRequested {
  param([string]$path)
  if (-not (Test-Path $path)) { return }
  if (-not $Backup) {
    Remove-Item -Recurse -Force $path
    return
  }
  $ts = Get-Date -Format 'yyyyMMddHHmmss'
  $backupPath = "$path.backup-$ts"
  Write-Host "  Backing up existing -> $backupPath" -ForegroundColor DarkGray
  Move-Item -LiteralPath $path -Destination $backupPath
}

Write-Host "Council Installer" -ForegroundColor White
Write-Host "=================" -ForegroundColor DarkGray
Write-Host "Council name: $CouncilName" -ForegroundColor Gray

$councilSlug = ConvertTo-Slug $CouncilName
Write-Host "Council slug: $councilSlug" -ForegroundColor Gray

# Load member rename map (optional)
$memberRenames = @{}
if ($MemberMap) {
  if (-not (Test-Path $MemberMap)) {
    Write-Host "Member map not found: $MemberMap" -ForegroundColor Red
    exit 1
  }
  try {
    $raw = Get-Content -Path $MemberMap -Raw | ConvertFrom-Json -AsHashtable
    foreach ($k in $raw.Keys) {
      if ($k.StartsWith('_')) { continue }
      $memberRenames[$k] = $raw[$k]
    }
    Write-Host "Member rename map loaded ($($memberRenames.Count) entries)" -ForegroundColor Gray
  } catch {
    Write-Host "Failed to parse member map JSON: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
  }
}

if ($Symlink -and ($RewriteReferences -or $memberRenames.Count -gt 0 -or $Backup)) {
  Write-Host "! -Symlink ignores -RewriteReferences, -MemberMap, and -Backup (junctions mirror the source repo)." -ForegroundColor Yellow
}

# Step 1: Resolve the target .claude/skills directory
$targetSkillsDir = $null

if ($DestinationPath) {
  if (Test-Path $DestinationPath) {
    $targetSkillsDir = $DestinationPath
  }
} else {
  Write-Host "Searching for accessibility-reviewer.md to locate active workspace..." -ForegroundColor Gray

  $searchPaths = [System.Collections.Generic.List[string]]::new()
  $searchPaths.Add($repoRoot)

  $current = $repoRoot
  for ($i = 0; $i -lt 3; $i++) {
    $current = Split-Path $current -Parent
    if ([string]::IsNullOrWhiteSpace($current)) { break }
    if ($searchPaths -notcontains $current) { $searchPaths.Add($current) }

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
  Write-Host "Could not find accessibility-reviewer.md automatically." -ForegroundColor Yellow
  $defaultPath = Join-Path $repoRoot ".claude/skills"
  $resp = Read-Host "Enter destination path for .claude/skills (Default: $defaultPath)"
  if ([string]::IsNullOrWhiteSpace($resp)) {
    $targetSkillsDir = $defaultPath
  } else {
    $targetSkillsDir = $resp
  }
}

if (-not (Test-Path $targetSkillsDir)) {
  New-Item -ItemType Directory -Path $targetSkillsDir -Force | Out-Null
}

# Derive workspace root from .claude/skills/... (parent of .claude)
$claudeDir = Split-Path $targetSkillsDir -Parent
$workspaceRoot = Split-Path $claudeDir -Parent
Write-Host "Workspace root: $workspaceRoot" -ForegroundColor Gray

# Council destination uses the branded slug
$councilDest = Join-Path $targetSkillsDir $councilSlug
Write-Host "Installing council to: $councilDest" -ForegroundColor Cyan
Backup-IfRequested $councilDest
if (-not (Test-Path $councilDest)) {
  New-Item -ItemType Directory -Path $councilDest -Force | Out-Null
}

# Copy or link council members (apply rename map)
$sourceCouncil = Join-Path $repoRoot "council"
$installedMembers = @()
if (Test-Path $sourceCouncil) {
  Get-ChildItem -Path $sourceCouncil -Directory | ForEach-Object {
    $srcName = $_.Name
    $destName = if ($memberRenames.ContainsKey($srcName)) { $memberRenames[$srcName] } else { $srcName }
    $dest = Join-Path $councilDest $destName
    Backup-IfRequested $dest
    if ($Symlink) {
      New-Item -ItemType Junction -Path $dest -Value $_.FullName | Out-Null
      Write-Host "  Junction: $srcName -> $destName" -ForegroundColor Gray
    } else {
      Copy-Item -Path $_.FullName -Destination $dest -Recurse -Force
      $marker = if ($destName -ne $srcName) { " (renamed from $srcName)" } else { "" }
      Write-Host "  Copied: $destName$marker" -ForegroundColor Gray
    }
    $installedMembers += [pscustomobject]@{ Source = $srcName; Dest = $destName; Path = $dest }
  }
}

# Copy optional files (council.md)
$sourceCouncilMd = Join-Path $sourceCouncil "council.md"
if (Test-Path $sourceCouncilMd) {
  Copy-Item -Path $sourceCouncilMd -Destination $councilDest -Force
  Write-Host "  Copied: council.md" -ForegroundColor Gray
}

# Copy companion skills (siblings to council dir under skills/)
Write-Host "Installing companion skills to $targetSkillsDir..." -ForegroundColor Cyan
$sourceSkills = Join-Path $repoRoot "skills"
if (Test-Path $sourceSkills) {
  Get-ChildItem -Path $sourceSkills -Directory | ForEach-Object {
    $dest = Join-Path $targetSkillsDir $_.Name
    Backup-IfRequested $dest
    if ($Symlink) {
      New-Item -ItemType Junction -Path $dest -Value $_.FullName | Out-Null
      Write-Host "  Junction: $($_.Name)" -ForegroundColor Gray
    } else {
      Copy-Item -Path $_.FullName -Destination $dest -Recurse -Force
      Write-Host "  Copied: $($_.Name)" -ForegroundColor Gray
    }
  }
}

# Copy SOP/procedures
if (-not $ProceduresPath) {
  $ProceduresPath = Join-Path $workspaceRoot "docs/procedures"
}
$sourceProcedures = Join-Path $repoRoot "procedures"
if (Test-Path $sourceProcedures) {
  if (-not (Test-Path $ProceduresPath)) {
    New-Item -ItemType Directory -Path $ProceduresPath -Force | Out-Null
  }
  Write-Host "Installing procedures to $ProceduresPath..." -ForegroundColor Cyan
  Copy-Item -Path "$sourceProcedures\*" -Destination $ProceduresPath -Recurse -Force
  Write-Host "  Installed procedures." -ForegroundColor Gray
}

# Optional reference rewriting
if ($RewriteReferences -and -not $Symlink) {
  Write-Host "Rewriting references in installed SKILL.md files..." -ForegroundColor Cyan
  $rewriteCount = 0
  $mdFiles = Get-ChildItem -Path $councilDest -Filter '*.md' -Recurse -File
  foreach ($f in $mdFiles) {
    $orig = Get-Content -Path $f.FullName -Raw
    $text = $orig
    # Rename member directory references
    foreach ($k in $memberRenames.Keys) {
      $v = $memberRenames[$k]
      if ($k -eq $v) { continue }
      # Match /the-foo/ or [the-foo] or `the-foo/SKILL.md` patterns conservatively
      $text = $text -replace ("(?<![A-Za-z0-9_-])" + [regex]::Escape($k) + "(?![A-Za-z0-9_-])"), $v
    }
    # Rename "The Council" to branded name
    if ($CouncilName -ne 'Council') {
      $text = $text -replace 'The Council', $CouncilName
    }
    if ($text -ne $orig) {
      Set-Content -Path $f.FullName -Value $text -NoNewline
      $rewriteCount++
    }
  }
  Write-Host "  Rewrote $rewriteCount file(s)." -ForegroundColor Gray
}

Write-Host ""
Write-Host "Installation successful." -ForegroundColor Green
Write-Host "  Council:    $councilDest" -ForegroundColor DarkGray
Write-Host "  Procedures: $ProceduresPath" -ForegroundColor DarkGray
if ($Backup) {
  Write-Host "  Backups:    *.backup-<timestamp> next to any clobbered dirs." -ForegroundColor DarkGray
}
