# Security Policy

The Council of Mikes is a documentation / skill-template library, not a runtime
service. That said, AI skill libraries do have a real attack surface — prompt
injection, skill spoofing, and routing hijacking can all turn well-intentioned
AI assistants into attack vectors.

This policy is curated by [The Sentinel](./council/the-sentinel/SKILL.md).

---

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.2.x   | ✅ Active |
| 1.1.x   | ⚠️ Critical fixes only |
| < 1.1   | ❌ Unsupported |

---

## What Counts as a Security Issue

Report privately if you find:

- **Prompt-injection vectors** in any SKILL.md, prompt, or AGENTS.md routing
  block that would let an attacker pivot an AI assistant into running
  unintended commands or revealing secrets.
- **Skill spoofing** — a way to make an AI assistant load a malicious skill
  with the same `name:` as a real Council member.
- **Routing hijacking** — a phrase or pattern that causes the Council router to
  load the wrong skill in a way that bypasses the Gatekeeper or Sentinel.
- **Hard-rule bypass** — anything that lets an AI agent skip the Pre-Submit
  Gate while still appearing to have run it.
- **Hidden / invisible characters** in skill files (zero-width spaces,
  RTL overrides, homoglyph substitutions in member names).

The following are **not** security issues — open a normal issue instead:

- A member gives wrong technical guidance (file a bug).
- A SOP phase is unclear (file a docs issue).
- You disagree with a routing decision (file a discussion).

---

## How to Report

**Do not open a public GitHub issue or PR for a vulnerability.**

Use GitHub's private vulnerability reporting:

1. Go to <https://github.com/underwms/council-of-mikes/security/advisories>
2. Click **Report a vulnerability**.
3. Include:
   - The file(s) affected.
   - A concrete reproduction (prompt + expected vs. actual AI behavior).
   - The blast radius (what an attacker could cause an adopter's AI to do).
   - Any suggested mitigation.

Expected response time: acknowledgement within 5 business days, triage within
10 business days. A coordinated-disclosure window will be negotiated for any
confirmed issue before public discussion.

---

## Scope Notes for Adopters

If you adopt the Council in your own repo and find a vulnerability that exists
only in your local configuration (e.g., your custom routing snippet leaks
secrets), that's a local issue — not a Council issue. Fix it locally and, if
the upstream snippet pattern enabled the mistake, send us a hardened version.

---

## Hardening Recommendations for Adopters

- Pin to a tagged release (e.g., `git submodule add ... && git -C council-of-mikes checkout v1.1.0`)
  rather than tracking `main`.
- Review every SKILL.md and prompt file diff when bumping versions.
- Never paste secrets, customer data, or production tokens into Council
  invocations — the Sentinel will flag PII but the Council is not a secrets
  vault.
- Treat any AI-generated PR that claims "Verdict: READY" without showing the
  full Gatekeeper Report as untrusted. Verify the gate actually ran.

---

## Credits

Vulnerability reporters who follow this policy will be credited (with consent)
in the relevant CHANGELOG entry and the GitHub advisory.
