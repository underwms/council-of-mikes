# Examples

Hand-picked transcripts that show the Council in action. Each example is a real interaction pattern — read them to see what the Council *feels* like, then steal the prompts.

| # | Scenario | Members involved | Skill demonstrated |
|---|---|---|---|
| [01](./01-architect-design-review.md) | Designing a new service before writing code | The Architect → The Curator → The Relay | **Brainstorm-first** workflow, specialist deference |
| [02](./02-purifier-quality-sweep.md) | The Purifier finds a SonarQube tripwire in a PR | The Coder → The Purifier → The Prover | **Quality-after-every-change** rule |
| [03](./03-gatekeeper-presubmit-gate.md) | The Gatekeeper blocks a "looks-done" change | The Gatekeeper | **11-phase Pre-Submit Gate** with a real BLOCKED verdict |

## How to read these

- Lines prefixed `>` are what the user typed.
- Lines prefixed with a Council member name are persona responses.
- Italic *(notes)* are editorial commentary, not part of the transcript.

## How to use these

1. **Copy the opening prompts** as starting templates for your own work.
2. **Watch the routing patterns** — note when one member explicitly hands off to another. That's the Council's core trick.
3. **Read the Gatekeeper transcript carefully** — it's the highest-leverage skill in the library. The bar it enforces is the difference between "tests passed" and "actually ready."

## Want to contribute an example?

Open an issue with the [new-feature template](../.github/ISSUE_TEMPLATE/feature_request.yml) describing the scenario, or PR a transcript directly. See [CONTRIBUTING.md](../CONTRIBUTING.md).
