<!--
  Council of Mikes — Pull Request Template
  Every PR must pass the 11-phase Pre-Submit Gate before merge.
  See: /procedures/code-change-pre-submit-sop.md and /council/the-gatekeeper/SKILL.md
-->

## Summary

<!-- One-paragraph description of WHAT changed and WHY. -->

## Type of Change

- [ ] 🐛 Bug fix (docs / SOP / routing error)
- [ ] ✨ New Council member or companion skill
- [ ] 📝 Documentation update (existing surface)
- [ ] 🔧 SOP / procedure change
- [ ] 🔐 Security-relevant change (also notify The Sentinel)
- [ ] ⚙️ CI / tooling / workflow change
- [ ] 💥 Breaking change (member rename, routing phrase change, SOP phase change)

## Affected Surfaces

<!-- Check every doc you touched OR confirm "no surface affected". -->

- [ ] `README.md`
- [ ] `AGENTS.md`
- [ ] `council/council.md`
- [ ] One or more `council/the-*/SKILL.md`
- [ ] One or more `skills/*/SKILL.md`
- [ ] `procedures/`
- [ ] `prompts/`
- [ ] `.github/copilot-instructions.md`
- [ ] `CHANGELOG.md` (Unreleased section updated)
- [ ] CI / `.github/workflows/`
- [ ] No documentation surface affected (justify in Summary)

## Doc-Lint

- [ ] `pwsh ./scripts/validate-council.ps1` passes locally
- [ ] Member count claims match the actual `council/the-*/SKILL.md` count
- [ ] All new SKILL.md files have YAML frontmatter (`name`, `description`)
- [ ] All new cross-references resolve

---

## Gatekeeper Report

<!--
  REQUIRED. Run @TheGatekeeper or /pre-submit on this diff and paste the
  resulting report below. PRs without a Gatekeeper Report ending in
  "Verdict: READY" will not be merged.

  See /council/the-gatekeeper/SKILL.md for the report format.
-->

```
Gatekeeper Report — <branch or change description>
--------------------------------------------------
Phase 1  Brainstorm:                    ✅ | ⚠️ | ❌ | n/a   notes:
Phase 2  Implement:                     ✅ | ⚠️ | ❌ | n/a   notes:
Phase 3  Purify:                        ✅ | ⚠️ | ❌ | n/a   notes:
Phase 4  Static analysis (no new lint): ✅ | ⚠️ | ❌ | n/a   notes:
Phase 5  Unit tests:                    ✅ | ⚠️ | ❌ | n/a   notes:
Phase 6  Coverage on changed lines:     ✅ | ⚠️ | ❌ | n/a   notes:
Phase 7  Regression (affected suite):   ✅ | ⚠️ | ❌ | n/a   notes:
Phase 8  Diff-vs-behavior review:       ✅ | ⚠️ | ❌         notes:
Phase 9  Integration & build:           ✅ | ⚠️ | ❌ | env   notes:
Phase 10 Copilot PR-review simulation:  ✅ | ⚠️ | ❌         notes:
Phase 11 Documentation update:          ✅ | ⚠️ | ❌ | n/a   notes:

Verdict: READY | BLOCKED
Blocking issues:
  - …
```

---

## Related Issues

<!-- Closes #N, Refs #M -->

## Reviewer Notes

<!-- Anything reviewers should pay particular attention to. Surprises, trade-offs, follow-ups. -->
