# Requirements, delivery evidence and backend observations

## Bounded-work authority and prospective exposure receipts (0.2.50)

Current readiness-policy planning/review and worker requests carry an explicit
start-work decision contract. Readiness owns its wording across consumers; assigned
engineers choose reversible local details using suitable observed repository patterns.
Declared substitutes may qualify current work without falsely satisfying final live
integration. Existing admission, approval, command, evidence and completion gates stand.

Provider-bound context receipts add finite call/role/operation linkage, UTC capture
time and a graph-request fingerprint. Old receipts remain readable without manufactured
linkage. No prompts or responses are logged, and graph-input identity does not establish
native wire delivery or semantic understanding. Control/candidate observations must
report actual findings and limits; clearer wording alone is not measured efficiency.

## Setup reliability (0.2.49)

Unchanged non-text baseline entries retain exact byte identity and no fabricated
text. Changed non-text content remains unapproved with a finite actionable diagnostic.
Legacy text baselines remain readable without rewriting them.

Supported .NET dependency discovery precedes inventory: the union of explicit command
projects and transitive references is fingerprinted with inherited configuration and
declared inputs. Unrelated sibling repositories are not traversed. Source roots share
the existing byte/traversal limits, and the v2 method identity invalidates v1 receipts.
Unsupported discovery uses the existing bounded runtime-mutable workspace fallback;
real relevant-source limits still stop admission.

Arbiter setup failures retain the initiating catalog code and graph stage in the private
checkpoint diagnostic. Existing finite node-failure events retain the original and
secondary failures separately. This adds no recovery authority or prompt logging.

## Proposal format admission (0.2.48)

Read-only structured proposal boundaries share one bounded format challenge:
initial roadmap/planning, intake, roadmap/plan reviews, arbiter classification,
investigation and finished-content review. Only trusted JSON/schema failures enter
this path; raw rejected responses and exception text never become correction input.
The corrected proposal passes the original contract and subsequent semantic guards.
No worker replay, human approval or source/freshness bypass is introduced. Intake
uses its cumulative draft budget; existing inspection and document-revision budgets
are not stacked with a new challenge. Exhausted malformed reviews block without
rewriting their candidate. Arbiter evidence permits only the failed format call and
its single successful correction between observation and admission.

## Arbiter adapter wiring (0.2.47)

Arbiter model input uses the standard chat message list, including one separately
validated shared-context frame. This repairs an immediate pre-process failure from
passing a raw dictionary to a chat adapter. Recovery actions and admission limits
are unchanged; the regression crosses the actual node/adapter/child-process seam.

## Native worker tool failure recovery (0.2.46)

`CODEX_EVENT_INVALID` stays a hard stop for invalid native event contracts. A failed
MCP item in an otherwise validated completed worker stream instead reports
`CODEX_TOOL_FAILED`. It is still a failed turn. All remaining events are validated,
and bounded file-change/usage facts are retained without raw tool payloads.

A matching worker/source observation admits a `tool_failure` incident to the
arbiter. Its choices are verification of retained partial work or stop. Verification
runs the accepted task commands; genuine failure then enters the existing
investigator/repair flow. The recorded arbiter call is permitted between observation
and admission, while unrelated calls or changed sources invalidate the binding.
Malformed streams, review-only tool use, permission/approval controls, source
boundaries and finite recovery budgets remain guarded. No blind worker replay or
native configuration change is introduced.

## Bounded proposal correction (0.2.45)

Parsed drafts that cite unobserved sources, lose an existing requirement identity
without retirement, or exceed the rendered document limit are not admitted.
Instead, the engine returns a finite reason and actual allowed sources/required
identities to the drafter, without repeating rejected content or requesting new
tools or human answers. Correction consumes the existing cumulative four-draft
budget. Valid revisions and prior documents remain unchanged until a replacement
passes validation, and every valid replacement still pauses for exact human
approval. `draft_rejections` retains finite reasons; exhaustion reports
`REQUIREMENTS_DRAFT_REJECTED` rather than an unclassified internal error.

## Live intake and recovery repairs (0.2.44)

Start grooming with `--requirements-file`, not the legacy positional prompt or
`--story` route. The initial draft and subsequent revisions pause at the requirements
gate even with autonomous planning enabled. The CLI emits JSON containing
`requirements_markdown`, the revision and exact `requirements_sha256`; it does not
currently provide a conversational input form. Review that Markdown, then resume
with a workspace-relative UTF-8 `--feedback-file` or explicitly approve the exact
hash. An operator monitoring the run can relay human feedback through that file.
Do not treat operator summaries or ordinary resume as approval.

An absent intake source now returns bounded missing-source feedback, so discovery
can continue within its existing inspection budget. Only successfully read source
bytes contribute observed hashes; permission, path-boundary and size guards remain.
The arbiter may classify a genuine roadmap-stage failure before roadmap acceptance,
without promoting the proposed roadmap to an accepted contract or permitting task
execution. Later-stage recovery retains its accepted-roadmap checks.

Read-only native turns disable both general and remote plugins and inherited
project-document loading, in addition to the existing isolated directory,
read-only sandbox and shell/apps controls. Strict native-tool event rejection
remains the acceptance boundary; configured isolation alone does not prove that a
native client cannot advertise any tool.

These extensions preserve the existing four model roles, configured native deadlines,
independent plan review and single arbiter. They do not create PRs, push, deploy,
resume historical runs or certify production identity and native hook trust.

## Submit, discuss and approve requirements

Run the installed interpreter with the selected workspace and a workspace-relative
Markdown file. The source template is packaged as `council/templates/requirements.md`;
installed execution never reads the temporary grooming template.

```powershell
$python = "$env:USERPROFILE/.council/runtime/Scripts/python.exe"
$workspace = "$env:USERPROFILE/workspace_root"
& $python -I -m council --workspace $workspace --requirements-file analysis.md --no-input
& $python -I -m council --workspace $workspace --resume RUN_ID --feedback-file feedback.md --no-input
& $python -I -m council --workspace $workspace --resume RUN_ID --approve-requirements EXACT_SHA256 --no-input
```

Council investigates read-only, presents a first draft, checkpoints and exits 2
while awaiting human input. The result includes the document, revision, SHA256
and actionable resume instructions. Feedback produces another draft. Approval
must name its exact hash; consequential unknowns require resolution or explicit
`--accept-limitation Q1` for a documented bounded default. Silence, ordinary resume,
`--auto-approve` and autonomous implementation-plan approval cannot approve it.

Original analysis remains unchanged. R/B/Q identifiers, explicit retirements,
meaningful revisions and human feedback persist in SQLite. Four drafting attempts,
four retained revisions and eight intake inspection rounds bound intake separately
from existing planning budgets. Native read-only transport retries retain their
existing finite policy. In-flight work lost before a checkpoint is not proof of
completed execution; operator reconciliation may still be necessary after a crash.

The canonical document covers purpose, scope/ownership, existing integration
patterns, behavior/business rules, data/lifecycle, acceptance examples, delivery
constraints and questions/decisions. Irrelevant sections should say why they are
not applicable. A small CLI need not invent entities, migrations or RATE rules.
For a lifecycle example, requirements may explicitly distinguish an active record,
its deletion and unknown pre-feature history without inventing retained snapshots.

Planning consumes the approved document and original rationale. A material human
scope question discovered in planning, or a finished-review scope-change finding,
returns to drafting and exact human approval. Model findings remain labeled model
proposals, not human answers. Reapproval archives prior delivery contracts and
receipt references, preserves execution/failure history and re-enters planning.
Historical contract changes still count against the original run budget.

## One baseline and coherent assignments

The shared context carries one requirements/baseline identity to intake, architecture,
roadmap and phase planning, readiness, coding, investigation, review, governance,
arbitration, verification and finalization. Context receipts retain artifact hashes.
Missing historical baselines remain `not_established`.

| Basis | Treatment |
| --- | --- |
| User-confirmed operating rule | Authoritative within scope; no external citation required |
| Repository observation | Hashes the exact bytes read; later source changes mark it stale |
| Proposal or unknown | Remains explicitly unconfirmed |
| Typed challenge | Names B/R identities, permitted reason, retained evidence and consequence |

Accepted plans can supply `baseline_challenges`. Independent review admits the
challenge metadata; it does not silently change human requirements. A
`requirement_change` returns to the human boundary. Failure/defect/dependency
challenges retain existing review and arbiter ownership. Structural references
are not a claim that a model's substantive reasoning is correct.
An independently accepted challenge can include a replacement repository fact and
source references. Current source hashes must match retained observations or named
verification inputs. A bounded amendment records the review identity and supersedes
the earlier observed interpretation in shared context, while the exact approved
Requirements document remains unchanged. User-confirmed rules cannot be amended
this way; unknown or stale evidence remains uncertainty rather than a new fact.

Reuse existing ReadPolicy/query filters and local Compose identity rather than
inventing production SSO or entitlement prerequisites. A new development-auth 403
is still an integration defect. Unsupported verification flags still require
reviewed command correction. Touched inherited inconsistencies do not authorize
unrelated cleanup, and equivalent implementations are acceptable.

An accepted task remains one coding assignment. Its internal inspect/test/edit/check
steps do not each become native calls. For example, one coherent CLI help change
can include discovery, a focused failing test, implementation and focused checks.
A separate persistence migration and API integration may warrant distinct reviewed
outcomes with dependency order. File count does not predict exact duration.

The bounded handoff distinguishes graph-observed file changes, current independent
receipt IDs and historical worker durations. Changed observations are not promoted
to current facts. Accepted plans, requirements, feedback and baseline decisions
remain accessible without relying on native conversation memory. Coders run focused
development checks; the independent prover executes accepted admission commands.
Expensive acceptance runs should not be duplicated mechanically. Timeout recovery
continues through the existing arbiter without raising the deadline.

## Proof scope and freshness

Optional task `proof_scope` version 1 names a workspace-relative project, explicit
generated inputs and runtime uncertainty. Supported simple .NET project metadata
resolves transitive ProjectReference closure and project-directory sources, shared
props/targets, configuration, manifests and lockfiles. Discovery is recomputed,
so additions, removals and dependency topology changes affect identity. Command,
working directory, accepted plan/contracts and approved requirements remain bound.
Toolchain observation includes the executable and selected SDK version where safe.

Conditional or imported/custom input topology, unsupported commands/ecosystems or
corrupt metadata fall back to bounded workspace source observation. Discovery does
not follow private/generated exclusions or links. Explicit consumed generated inputs
cannot disappear silently: unavailable/protected inputs prevent admission. Incidental
coverage/capture outputs remain excluded. Inventory or complete-review bounds fail
explicitly rather than approving truncated input.

Source hashes cannot certify mutable services, databases or fixtures. Test commands,
fallback scopes and unavailable toolchain identity conservatively require a fresh
delivery boundary even if a model requests `runtime_mutable=false`. No model can
assert unknown runtime independence. Finer ecosystem and runtime scopes remain
unsupported until tooling supplies trustworthy evidence.

An unrelated-project edit can preserve a receipt within its supported boundary;
a referenced shared helper or configuration edit invalidates it. Mid-command input
changes fail admission. Reuse retains the original execution identity and result.
Old receipts retain their legacy source semantics; they are not retroactively narrowed.
Task, phase, final audit and arbiter refresh use the common validity resolver.
Finalization also checks completed pieces' saved contracts and restores stale pieces
for normal approved verification rather than certifying only the last plan.

## Actual finalization and qualified readiness

Autonomous requirements submissions include finalization. Legacy prompt/story routes
remain unchanged unless a new autonomous run requests `--finalize`. Policy is fixed
at creation; a resume cannot add this flag. Manual/bypass requirements intake still
enforces human requirements approval and retains its existing delivery route.

The final accepted phase plan ends with a `delivery_stage=finalize` task: actual
code-capable scoped polish and documentation inspection, followed by independent
prover execution. The missing/wrong-stage preflight offers a bounded correction.
Canonical Purifier/Codex guidance and the complete feature input reach the author.
Inspected-no-edit is valid; stage names alone do not establish quality work.

Before editing, bounded private baseline artifacts preserve original module content
and repository identities. Overlapping scopes cannot rebase away new feature files.
Finished review includes before/after content, new/deleted files, requirements,
contract/evidence identities, gate evidence and retained findings. Unattributed
concurrent changes, repository identity changes or oversized/incomplete content
prevent unqualified approval. Private review content is never explanatory telemetry.

A separate configured reviewer inspects correctness, integration, maintainability,
tests and documentation under Gatekeeper guidance. Acceptance binds the exact
content/evidence packet and becomes stale after edits or evidence changes. Located,
stable findings require concrete consequences. Repairs use the existing arbiter,
accepted polish task and actual verification, followed by re-review. Three completed
finished reviews and existing recovery/step budgets bound this work.

| SOP phase | Evidence used by delivery |
| --- | --- |
| 1 Brainstorm | Accepted independently reviewed plan/architecture |
| 2 Implement | Completed accepted tasks with current receipts |
| 3 Purify | Actual polish assignment plus independently inspected dimension |
| 4 Static analysis | Reviewed quality-gate task obligations and actual current executions |
| 5 Unit tests | Reviewed quality-gate task obligations and actual current executions |
| 6 Coverage validation | Reviewed scope/metric obligations and actual current executions |
| 7 Regression | Reviewed quality-gate task obligations and actual current executions |
| 8 Diff vs behavior | Independent complete finished-content review |
| 9 Integration/build | Reviewed quality-gate task obligations and actual current executions |
| 10 PR-review simulation | Independent finished-content decision and resolved findings |
| 11 Documentation | Actual documentation inspection plus independently inspected dimension |

Final plans may map the five executable gate categories to accepted task IDs through
`quality_gates`, or state a concrete reviewed out-of-scope reason. Independent review
must check that these obligations establish their named metrics; an exit-zero command
name is not semantic proof. Missing/failed/stale evidence remains unverified.
`delivery_result.functional_complete` and `delivery_result.pr_ready` are separate.
Functional completion can be qualified while PR readiness remains false. Neither
field creates a PR, merge or deployment.
The exact approved document also names `completion_boundary`: `functional` or
`pr_ready`. A stronger approved PR-readiness boundary cannot finish successfully
with missing quality evidence; the engine reports `DELIVERY_BOUNDARY_NOT_MET`.

## Backend observation contract v1

Existing safe diagnostics remain the event source. A bounded SQLite store at the
selected engine memory root's `observability.sqlite` records versioned observations;
it is not a scheduler or admission controller. Existing databases/checkpoints are
not migrated into invented history. Schema 1 creates separate observation tables;
an unsupported schema remains unavailable.

The existing loopback viewer backend exposes GET-only paths for its selected run:

```text
/api/v1/runs/RUN_ID/summary
/api/v1/runs/RUN_ID/summary?group_by=role
/api/v1/runs/RUN_ID/events?after=0&limit=100
/api/v1/runs/RUN_ID/milestones?after=0&limit=100
/api/v1/runs/RUN_ID/calls?after=0&limit=100
/api/v1/runs/RUN_ID/commands?after=0&limit=100
/api/v1/runs/RUN_ID/sessions?after=0&limit=100
/api/v1/runs/RUN_ID/export?after=0&limit=100
```

Other supported grouping dimensions are operation, provider, requested_model and
reported_model. A requested model never fills an unreported effective model.
Unknowns use null. Export is machine-readable paginated events, not a checkpoint dump.
Invalid queries return 400; another run returns 404; foreign origins/non-loopback
hosts return 403. Missing/unsupported storage returns a bounded status object.

`position`/`next_cursor` are stable ingestion cursors. Use session_generation plus
source_seq for causal replay and insertion of delayed observations. Session IDs,
source event IDs and verification execution IDs provide safe provenance. Duplicate
delivery is idempotent; changed content under one identity is rejected. Older-session
events cannot overwrite newer current status. Milestones include deterministic
explanations. Model interpretation is disabled: deterministic coverage provides
low-latency status without another provider, budget or failure dependency. Model
interpretation has no measured benefit here and would require separate evaluation.

Example current status:

```json
{"version":1,"liveness":"unknown","coverage":"prospective_events_only","current":{"state":"verification_pending","message":"Coding turn finished; independent verification is pending."},"wall_time_seconds":null,"unclassified_gaps":true}
```

Usage is per-attempt reported input/output/total/cached-input counts, including
available failed-attempt usage. Totals are not manufactured from unlike categories.
Each aggregate reports measured/missing/partial attempts and per-field populations.
Missing measurements remain null, not zero or estimated billing. Median durations
use the ordinary sorted middle/mean-of-two rule with a measured population count.
Comparison metadata records installed-distribution version separately from the
executed graph module hash, requirements/accepted-plan/obligation hashes, recorded
policies and configured role/model/deadline choices. Per-attempt effective deadlines
remain separate from those configuration values.
Inclusive node/call/command durations overlap and must not be added as wall time.
Graph-owned commands record actual UTC endpoints and monotonic duration, correlated
to their original execution receipts. Native internal command timings remain unknown.
Explicit human-wait endpoints can span sessions; ordinary session gaps remain
unclassified. Session end alone never means run completion or process death.

Persistence caps are 8,192 events per run, 100,000 events and 1,024 process sessions
per database; pages are at most 200 items and groups at most 64. Capacity/permission
failures surface incomplete/unavailable observation coverage under existing diagnostic
policy, while execution and its independent evidence remain authoritative. Read-only
backend probes cap database size at 128 MiB. No automatic deletion of active evidence
or background interpretation process is introduced. Operators can archive a closed
private store; historical gaps must remain disclosed.

For triage, retrieve grouped summary, then calls/commands and adjacent event pages by
cursor. Preserve all pages of export for retrospective comparison. Compare acceptance
scope, requirements identity, configured models/deadlines and missing measurements
before interpreting differences. RATE is historical evidence, not a counterfactual
runtime-saving or general reliability benchmark. No frontend files are changed.

## Provisioning marker

The existing PowerShell provisioning strategy and dependency pins remain intact.
The helper reads installed `council-orchestrator` distribution metadata, compares it
with the source project's expected version, and publishes the successful marker
atomically after pip/doctor checks. Other marker fields survive. Validation separates
missing/invalid marker, unavailable metadata, expected-target mismatch and
marker/distribution mismatch. It never rewrites disagreement to conceal it.
Version matching uses normalized PEP 440 equality; the marker retains the actual
installed distribution's version string.

PowerShell provisioning still requires PowerShell 7. The local verified-wheel release
procedure can install with the existing interpreter without dependency resolution.
Always check active Council processes before replacing a runtime. Placement, installed
package identity, offline doctor, native hook trust and live provider access remain
separate claims.
