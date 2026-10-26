# Requirements document: [Name]

**Status:** Draft / In discussion / Approved for planning  
**Initial analysis:** [Reference to the original Markdown input]

## 1. Purpose and desired outcome

- **Problem:** What is happening today, and why does it need to change?
- **Desired outcome:** What should become possible or improve?
- **Affected users or systems:** Who or what benefits?
- **Success:** What observable result would demonstrate that the problem is solved?

Preserve the intent and reasoning from the initial analysis. Identify proposed interpretations explicitly.

## 2. Scope and ownership

- **Included:** Behaviors and outcomes this effort must deliver.
- **Excluded:** Relevant work explicitly outside this effort.
- **Existing capabilities to reuse:** Established behavior this feature should build on.
- **Other owners:** Related work supplied by another team, developer or agent.
- **Dependencies:** What must exist before this work can succeed?

Distinguish confirmed dependencies from suspected dependencies requiring investigation.

## 3. Existing patterns and integration context

Summarize relevant findings from the current application and documentation:

| Existing pattern or contract | Evidence | Implication for this work |
| --- | --- | --- |
| [Pattern or contract] | [Source reference] | [Reuse, extend, or proposed change] |

Consider relevant data structures, interfaces, user flows, authorization, development workflows and verification conventions.

Explain any proposed departure from an existing pattern. Existing inconsistencies become additional work only when necessary for the agreed outcome or explicitly included in scope.

## 4. Required behavior and business rules

Give each requirement a stable identifier for discussion and later verification.

| ID | Required behavior or rule | Basis |
| --- | --- | --- |
| R1 | [Observable behavior or explicit constraint] | [User input, confirmed decision, repository evidence, or proposal] |

Where relevant, describe:

- User and domain terminology.
- Inputs, outputs and meaningful defaults.
- Validation, empty results, unavailable information and failure behavior.
- Access and ownership boundaries.
- Compatibility with existing behavior.

Keep proposed choices visibly separate from confirmed requirements.

## 5. Data, relationships and lifecycle

Complete the portions relevant to this effort.

- **Source of truth:** Where authoritative information comes from.
- **Writes and ownership:** What this effort changes and who supplies other data.
- **Relationships:** Grouping, cardinality, identity and uniqueness rules.
- **Lifecycle:** Relevant transitions and what survives each transition.
- **Historical behavior:** What can be reconstructed and what must remain unknown.
- **Time and boundaries:** Relevant timezone, ordering and exact-boundary semantics.

Use a small example or transition table when it makes these rules clearer. Identify missing evidence rather than inventing data or business rules.

## 6. Acceptance examples

Describe concrete examples that establish the intended behavior.

| Example | Starting conditions | Action or event | Expected observable result | Requirements covered |
| --- | --- | --- | --- | --- |
| A1 | [Conditions] | [Action] | [Result] | [R1] |

Include the normal case and consequential boundary, failure or compatibility cases. Use representative data where identity, grouping or lifecycle affects correctness.

Examples express required outcomes without prescribing routine implementation details.

## 7. Verification and delivery constraints

- **Acceptance environment:** Where the result must be demonstrated.
- **Existing verification approach:** Relevant established tests, tools and workflows.
- **Required evidence:** What must be shown to establish acceptance.
- **Operational constraints:** Relevant security, performance, compatibility, resource or deployment requirements.
- **Completion boundary:** What this effort must deliver—for example, verified local behavior, a reviewable PR, or deployment.

Separate environment readiness from verification of behavior that does not exist yet. Council planning will establish executable commands and dependency order.

## 8. Questions, decisions and approval

### Open questions

| Question | Why the answer matters | Proposed answer, if supported | Who can resolve it? |
| --- | --- | --- | --- |
| [Question] | [Effect on behavior, scope or acceptance] | [Proposal or Unknown] | [User / repository investigation / external owner] |

### Agreed decisions

Record consequential decisions and their rationale. Update the relevant requirements when a decision changes them.

### Approval for planning

Record the user’s explicit approval of the Requirements document and any accepted limitations or deferred questions.

Unknowns affecting correctness, scope, authority or acceptance must be resolved or explicitly bounded before planning. Routine implementation choices may remain with the implementing agent.
