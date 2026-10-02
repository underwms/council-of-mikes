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
      5. [[wikilinks]] resolve to a Council member, companion skill, or .md file.
      6. No employer-specific fingerprints leak into adopter-facing files.
      7. `@.claude/skills/...` paths used in prompts/AGENTS/copilot-instructions
         resolve to real source files (council/<member>/ or skills/<name>/).
      8. Backtick-wrapped `procedures/*.md` and `skills/*/SKILL.md` references
         resolve to real files (catches refs that aren't formatted as MD links).

    Run locally before pushing; CI runs the same script via doc-lint workflow.

.EXAMPLE
    pwsh ./scripts/validate-council.ps1
#>

[CmdletBinding()]
param(
    [string]$RepoRoot,
    [string]$FingerprintPattern
)

if ([string]::IsNullOrEmpty($RepoRoot)) {
    if (-not [string]::IsNullOrEmpty($PSScriptRoot)) {
        $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    } else {
        $RepoRoot = (Get-Location).Path
    }
}

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
Write-Host "[1/8] SKILL.md frontmatter"
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
Write-Host "`n[2/8] Member-count consistency"
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
Write-Host "`n[3/8] Pre-Submit phase-count consistency (must be 11-phase)"
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
Write-Host "`n[4/8] Internal Markdown link resolution"
$linkFails = $failures.Count
$mdFiles = Get-ChildItem -Path $RepoRoot -Filter '*.md' -Recurse -File |
    Where-Object { $_.FullName -notmatch '\\\.git\\' }

$linkPattern = '\[[^\]]+\]\((?<target>[^)]+)\)'
foreach ($md in $mdFiles) {
    $text = Get-Content -Path $md.FullName -Raw
    # Strip fenced code blocks and inline-code spans so example link syntax
    # in prose (e.g., `[text](url)`) doesn't get treated as a real link.
    $stripped = [regex]::Replace($text, '(?s)```.*?```', '')
    $stripped = [regex]::Replace($stripped, '`[^`\n]*`', '')
    foreach ($match in [regex]::Matches($stripped, $linkPattern)) {
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

# ─── Check 5: Wikilink resolution ────────────────────────────────────────────
Write-Host "`n[5/8] Wikilink resolution"
$wlFails = $failures.Count

# Build an index of resolvable wikilink targets.
#   - Council member dirs (council/the-X/) resolve via short name `the-X`.
#   - Companion skills (skills/X/) resolve via `X`.
#   - Any .md file is reachable by its stem.
$wlIndex = @{}
foreach ($d in (Get-ChildItem (Join-Path $RepoRoot 'council') -Directory -ErrorAction SilentlyContinue)) {
    $wlIndex[$d.Name] = $true
}
foreach ($d in (Get-ChildItem (Join-Path $RepoRoot 'skills') -Directory -ErrorAction SilentlyContinue)) {
    $wlIndex[$d.Name] = $true
}
foreach ($md in (Get-ChildItem -Path $RepoRoot -Filter '*.md' -Recurse -File | Where-Object { $_.FullName -notmatch '\\\.git\\' })) {
    $wlIndex[$md.BaseName] = $true
}

# Match [[target]] or [[target|alias]]. Skip code-fenced backticks.
$wlPattern = '(?<![`\\])\[\[(?<target>[^\]\|`#]+?)(?:\\?\|[^\]`]+)?(?:#[^\]`]+)?\]\](?!`)'
foreach ($md in $mdFiles) {
    $text = Get-Content -Path $md.FullName -Raw
    foreach ($match in [regex]::Matches($text, $wlPattern)) {
        $target = $match.Groups['target'].Value.Trim().TrimEnd('\')
        if ($target.StartsWith('<') -and $target.EndsWith('>')) { continue }
        if (-not $wlIndex.ContainsKey($target)) {
            $rel = $md.FullName -replace [regex]::Escape($RepoRoot + [IO.Path]::DirectorySeparatorChar), ''
            Add-Failure "$rel → broken wikilink: [[$target]]"
        }
    }
}
if ($failures.Count -eq $wlFails) {
    Add-Pass "All [[wikilinks]] resolve to a Council member, companion skill, or markdown file"
}

# ─── Check 6: No employer-specific fingerprints ──────────────────────────────
Write-Host "`n[6/8] No employer-specific fingerprints"
$fpFails = $failures.Count
# Configurable scan list. Override via -FingerprintPattern parameter or the
# COUNCIL_FINGERPRINT_PATTERN env var with a regex matching the strings that
# must never leak into your fork (e.g., 'acme|acme-internal|acme.com').
# By default the check is disabled because there is no universal pattern that
# is right for every adopter.
if (-not $FingerprintPattern) {
    $FingerprintPattern = $env:COUNCIL_FINGERPRINT_PATTERN
}
if (-not $FingerprintPattern) {
    Add-Pass "Skipped (no -FingerprintPattern set; export COUNCIL_FINGERPRINT_PATTERN to enable)"
}
else {
    $fpPattern = $FingerprintPattern
    $fpAllowlist = @(
        (Join-Path $RepoRoot 'CONTRIBUTING.md'),
        (Join-Path $RepoRoot 'SECURITY.md'),
        (Join-Path $RepoRoot '.github\PULL_REQUEST_TEMPLATE.md'),
        (Join-Path $RepoRoot '.github\workflows\doc-lint.yml'),
        (Join-Path $RepoRoot 'scripts\validate-council.ps1')
    )
    $fpScan = Get-ChildItem -Path $RepoRoot -Recurse -File -Include *.md,*.ps1,*.yml,*.yaml |
        Where-Object { $_.FullName -notmatch '\\\.git\\' -and $fpAllowlist -notcontains $_.FullName }
    foreach ($f in $fpScan) {
        $matches = Select-String -Path $f.FullName -Pattern $fpPattern -CaseSensitive:$false
        foreach ($m in $matches) {
            $rel = $f.FullName -replace [regex]::Escape($RepoRoot + [IO.Path]::DirectorySeparatorChar), ''
            Add-Failure "${rel}:$($m.LineNumber) → employer-specific fingerprint: $($m.Line.Trim())"
        }
    }
    if ($failures.Count -eq $fpFails) {
        Add-Pass "No employer-specific fingerprints found (pattern: $fpPattern)"
    }
}

# ─── Check 7: @.claude/skills/... references resolve ─────────────────────────
# Adopter-facing docs use `@.claude/skills/council/the-X/SKILL.md` and
# `@.claude/skills/<companion>/SKILL.md` to describe where files land in a
# consumer workspace. Map those back to source paths and verify they exist.
Write-Host "`n[7/8] @.claude/skills/... reference resolution"
$atFails = $failures.Count
$atPattern = '@\.claude/skills/(?<rest>[A-Za-z0-9_./\-]+)'
foreach ($md in $mdFiles) {
    $text = Get-Content -Path $md.FullName -Raw
    $stripped = [regex]::Replace($text, '(?s)```.*?```', '')
    foreach ($match in [regex]::Matches($stripped, $atPattern)) {
        $rest = $match.Groups['rest'].Value.TrimEnd('.',',',';',':',')')
        # council/<member>/... → <member>/... under council/
        # <other>/...          → <other>/... under skills/
        if ($rest -match '^council/(.+)$') {
            $sourceRel = Join-Path 'council' $Matches[1]
        } else {
            $sourceRel = Join-Path 'skills' $rest
        }
        $sourcePath = Join-Path $RepoRoot $sourceRel
        if (-not (Test-Path -LiteralPath $sourcePath)) {
            $rel = $md.FullName -replace [regex]::Escape($RepoRoot + [IO.Path]::DirectorySeparatorChar), ''
            Add-Failure "${rel} → @.claude/skills/$rest does not resolve to $sourceRel"
        }
    }
}
if ($failures.Count -eq $atFails) {
    Add-Pass "All @.claude/skills/... references resolve to source files"
}

# ─── Check 8: backtick-wrapped procedure / skill references ──────────────────
# Catches refs like `procedures/code-change-pre-submit-sop.md` and
# `council/the-X/SKILL.md` that aren't formatted as Markdown links and would
# slip past Check 4.
Write-Host "`n[8/8] Backtick-wrapped path references"
$btFails = $failures.Count
$btPattern = '`(?<path>(?:procedures|council|skills)/[A-Za-z0-9_./\-]+\.md)`'
foreach ($md in $mdFiles) {
    $text = Get-Content -Path $md.FullName -Raw
    $stripped = [regex]::Replace($text, '(?s)```.*?```', '')
    foreach ($match in [regex]::Matches($stripped, $btPattern)) {
        $p = $match.Groups['path'].Value
        $full = Join-Path $RepoRoot $p
        if (-not (Test-Path -LiteralPath $full)) {
            $rel = $md.FullName -replace [regex]::Escape($RepoRoot + [IO.Path]::DirectorySeparatorChar), ''
            Add-Failure "${rel} → backtick path does not resolve: $p"
        }
    }
}
if ($failures.Count -eq $btFails) {
    Add-Pass "All backtick-wrapped procedure/skill refs resolve"
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
