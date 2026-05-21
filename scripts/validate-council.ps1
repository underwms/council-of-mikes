<#
.SYNOPSIS
    Validates the Council of Mikes documentation for structural consistency.

.DESCRIPTION
    Runs a series of checks against the repository:
      1. Every council/the-*/SKILL.md has YAML frontmatter with required keys.
      2. Member-count claims in README.md, AGENTS.md, council/council.md, and
         .github/copilot-instructions.md match the actual SKILL.md file count.
      3. The Pre-Submit SOP uses "11-phase" consistently (no "10-phase" stragglers).
      4. Internal Markdown links resolve to real files.

    Run locally before pushing; CI runs the same script via doc-lint workflow.

.EXAMPLE
    pwsh ./scripts/validate-council.ps1
#>

[CmdletBinding()]
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$ErrorActionPreference = 'Stop'
$failures = New-Object System.Collections.Generic.List[string]

function Add-Failure {
    param([string]$Message)
    $script:failures.Add($Message)
    Write-Host "  ✗ $Message" -ForegroundColor Red
}

function Add-Pass {
    param([string]$Message)
    Write-Host "  ✓ $Message" -ForegroundColor Green
}

Write-Host "Council of Mikes — doc-lint" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"
Write-Host ""

# ─── Check 1: SKILL.md frontmatter ───────────────────────────────────────────
Write-Host "[1/4] SKILL.md frontmatter"
$councilSkills = Get-ChildItem -Path (Join-Path $RepoRoot 'council') -Filter 'SKILL.md' -Recurse
foreach ($skill in $councilSkills) {
    $content = Get-Content -Path $skill.FullName -Raw
    if ($content -notmatch "(?ms)\A---\s*\r?\n.*?\r?\n---\s*\r?\n") {
        Add-Failure "$($skill.FullName -replace [regex]::Escape($RepoRoot + [IO.Path]::DirectorySeparatorChar), '') missing YAML frontmatter block"
        continue
    }
    $frontmatter = ($content -split "---", 3)[1]
    if ($frontmatter -notmatch "(?m)^\s*name:\s*\S+") {
        Add-Failure "$($skill.Directory.Name) frontmatter missing 'name:' key"
    }
    if ($frontmatter -notmatch "(?m)^\s*description:\s*\S+") {
        Add-Failure "$($skill.Directory.Name) frontmatter missing 'description:' key"
    }
}
if ($failures.Count -eq 0) {
    Add-Pass "All $($councilSkills.Count) Council member SKILL.md files have valid frontmatter"
}

# Also check companion skills/* SKILL.md files
$companionSkills = Get-ChildItem -Path (Join-Path $RepoRoot 'skills') -Filter 'SKILL.md' -Recurse -ErrorAction SilentlyContinue
$companionFails = $failures.Count
foreach ($skill in $companionSkills) {
    $content = Get-Content -Path $skill.FullName -Raw
    if ($content -notmatch "(?ms)\A---\s*\r?\n.*?\r?\n---\s*\r?\n") {
        Add-Failure "$($skill.FullName -replace [regex]::Escape($RepoRoot + [IO.Path]::DirectorySeparatorChar), '') (companion skill) missing YAML frontmatter"
    }
}
if ($failures.Count -eq $companionFails) {
    Add-Pass "All $($companionSkills.Count) companion skills have frontmatter"
}

# ─── Check 2: Member-count consistency ───────────────────────────────────────
Write-Host "`n[2/4] Member-count consistency"
$expectedCount = $councilSkills.Count
$countFails = $failures.Count

$readmeContent      = Get-Content (Join-Path $RepoRoot 'README.md') -Raw
$agentsContent      = Get-Content (Join-Path $RepoRoot 'AGENTS.md') -Raw
$councilContent     = Get-Content (Join-Path $RepoRoot 'council/council.md') -Raw
$copilotContent     = Get-Content (Join-Path $RepoRoot '.github/copilot-instructions.md') -Raw

$claimPattern = '(?:Members \()?(\d+)(?:\))?(?:\s+(?:AI\s+)?expert\s+(?:AI\s+)?personas)?'

# README.md: look for "## Members (N)" and the prose "N AI expert personas"
if ($readmeContent -notmatch "## Members \($expectedCount\)") {
    Add-Failure "README.md '## Members (N)' header does not say $expectedCount"
}
if ($readmeContent -notmatch "team of $expectedCount AI expert personas") {
    Add-Failure "README.md tagline does not mention '$expectedCount AI expert personas'"
}

# council/council.md: "## Members (N)"
if ($councilContent -notmatch "## Members \($expectedCount\)") {
    Add-Failure "council/council.md '## Members (N)' header does not say $expectedCount"
}

# AGENTS.md: "**N expert AI personas**"
if ($agentsContent -notmatch "\*\*$expectedCount expert AI personas\*\*") {
    Add-Failure "AGENTS.md does not mention '$expectedCount expert AI personas'"
}

# copilot-instructions: "**N AI expert personas**"
if ($copilotContent -notmatch "\*\*$expectedCount AI expert personas\*\*") {
    Add-Failure ".github/copilot-instructions.md does not mention '$expectedCount AI expert personas'"
}

if ($failures.Count -eq $countFails) {
    Add-Pass "All docs claim $expectedCount members and SKILL.md count matches"
}

# ─── Check 3: Pre-Submit phase count consistency ─────────────────────────────
Write-Host "`n[3/4] Pre-Submit phase-count consistency (must be 11-phase)"
$phaseFails = $failures.Count
$sopFiles = @(
    'procedures/code-change-pre-submit-sop.md',
    'council/the-gatekeeper/SKILL.md',
    'README.md',
    'AGENTS.md',
    '.github/copilot-instructions.md'
)
foreach ($rel in $sopFiles) {
    $path = Join-Path $RepoRoot $rel
    if (-not (Test-Path $path)) { continue }
    $text = Get-Content -Path $path -Raw
    if ($text -match '10-phase Pre-Submit' -or $text -match 'full 10 phases' -or $text -match 'after Phase 10 may an agent report') {
        Add-Failure "$rel contains stale 10-phase wording (should be 11-phase)"
    }
}
if ($failures.Count -eq $phaseFails) {
    Add-Pass "No 10-phase stragglers; gate is consistently 11-phase"
}

# ─── Check 4: Internal Markdown links ────────────────────────────────────────
Write-Host "`n[4/4] Internal Markdown link resolution"
$linkFails = $failures.Count
$mdFiles = Get-ChildItem -Path $RepoRoot -Filter '*.md' -Recurse -File |
    Where-Object { $_.FullName -notmatch '\\\.git\\' }

$linkPattern = '\[[^\]]+\]\((?<target>[^)]+)\)'
foreach ($md in $mdFiles) {
    $text = Get-Content -Path $md.FullName -Raw
    foreach ($match in [regex]::Matches($text, $linkPattern)) {
        $target = $match.Groups['target'].Value.Trim()
        if ($target -match '^(https?:|mailto:|#)') { continue }
        if ($target -match '^<.*>$') { continue }
        # Skip absolute-path links: in skill-library context, leading `/` is a
        # convention for "adopter's workspace root", not this repo. Those are
        # validated by the adopter, not by us.
        if ($target.StartsWith('/')) { continue }
        # strip anchor fragment
        $file = ($target -split '#', 2)[0]
        if ([string]::IsNullOrWhiteSpace($file)) { continue }
        $resolved = Join-Path -Path $md.Directory.FullName -ChildPath $file
        if (-not (Test-Path -LiteralPath $resolved)) {
            $rel = $md.FullName -replace [regex]::Escape($RepoRoot + [IO.Path]::DirectorySeparatorChar), ''
            Add-Failure "$rel → broken link: $target"
        }
    }
}
if ($failures.Count -eq $linkFails) {
    Add-Pass "All internal Markdown links resolve"
}

# ─── Summary ─────────────────────────────────────────────────────────────────
Write-Host ""
if ($failures.Count -gt 0) {
    Write-Host "FAILED — $($failures.Count) issue(s):" -ForegroundColor Red
    $failures | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    exit 1
}

Write-Host "PASS — Council documentation is consistent." -ForegroundColor Green
exit 0
