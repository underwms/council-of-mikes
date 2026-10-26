# Council orchestration engine

## Shared proof command admission (0.2.57)

Plan preflight and proof discovery share the supported literal .NET command
grammar. Empty trailing `dotnet run --` separators are accepted; unresolved
runtime/property arguments receive located planner feedback before dispatch.
Literal `.slnx` builds include their declared projects, including the observed
Aspire host and Docker SDKs. Exact `git diff --check` observes the full affected
repository while retaining cross-repository project dependencies. Hosting,
container, run, test and Git observations remain runtime mutable. Unknown
relationships retain conservative fallback; inventory budgets are unchanged.

## File-target admission and explicit .NET run proofs (0.2.56)

Plan preflight rejects existing directories and other non-file edit targets with
located `PLAN_TARGET_PATH_INVALID` feedback before review or worker dispatch.
Individual not-yet-generated files remain valid targets; native filesystem
permission denials remain denials. Planner and reviewer receive the same file-only
target contract.

Explicit `dotnet run --project <file.csproj>` verification uses the existing bounded
transitive project closure, including MSTest SDK projects. Run receipts are always
runtime-mutable. Unresolved application arguments or implicit project selection
retain conservative fallback. No inventory budgets or evidence rules are relaxed.

## Certified native reasoning isolation (0.2.55)

Every native read-only reasoning/review turn now reduces the selected bundled
model's tool-capability metadata in a temporary per-turn catalog, preserving its
model ID and non-tool metadata. This handles model-selected code mode and
multi-agent V2, which generic feature switches alone did not suppress. Worker
coding turns retain their existing permissions and launch path.

Before any reasoning model request, an offline prompt inventory must establish
zero native tools with the same model/catalog/tool controls. Its diagnostic home
is empty; no credentials are copied. Actual execution retains the original login,
ignores user config, uses the read-only sandbox and starts without the shared
daemon so the startup-only catalog takes effect. Temporary artifacts are removed
after the turn. Unknown models, malformed metadata/inventories or exposed tools
fail closed with `CODEX_REVIEW_ISOLATION_FAILED`; the program stops without asking
an arbiter to override that configuration boundary. Strict rejection of any
unexpected native tool event remains active.

This relies on the installed CLI's catalog and prompt-inventory contracts; a
future unsupported contract must fail preflight rather than silently reuse the
old argument-only assumption. It does not alter user configuration, authentication,
managed restrictions, graph routes or historical checkpoints.

## Bounded MSTest implementation proof discovery (0.2.54)

Implementation proof discovery supports the existing `MSTest.Sdk` project topology,
project-local source/content selectors and literal `RunSettingsFilePath` inputs,
including `$(MSBuildThisFileDirectory)`. Optional settings are fingerprinted as
absent or present even when guarded by a condition. Relevant project, source,
seed, SDK configuration and settings edits invalidate the receipt.

The resolver inventories the transitive project directories and inherited metadata;
it does not scan unrelated repositories for these supported forms. Unknown SDKs,
imports, dynamic paths and conditions affecting dependency topology retain the
conservative fallback. Traversal/byte/receipt bounds, private-path and link guards,
native permission denials and runtime-mutability checks remain binding. This repair
changes neither graph routing nor historical checkpoints and does not establish
application test success.

## Established baseline and targeted readiness (0.2.53)

Fresh autonomous runs use readiness policy 3. Established infrastructure is the working
baseline unless the requested change materially affects it, relevant evidence shows a
failure, or the user requests requalification. Implementation-only plans are valid.
Optional readiness tasks prepare specific later consumers; they need not cover unrelated
work. A new generic DI, migration or database CRUD harness is not a permission-to-start
gate. Engineers own routine fixture and supported local development setup.

Feature verification, permissions, approved contracts, frozen tests, source freshness and
final acceptance remain binding. No-readiness plans report `not_required`, rather than
claiming fresh environment qualification. Persisted policy 1/2 runs retain their recorded
semantics; policy 2's mandatory prefix is not silently reinterpreted.

This release also includes the separately developed persisted node narration and ticker.
Narration observes lifecycle events out of band, has no execution authority, and falls
back to recorded event summaries when unavailable. Its model usage is separate from task
execution. Set `COUNCIL_NARRATION_ENABLED=0` to disable generation; regression tests opt
in only with an inert provider boundary. Older runs are not retroactively narrated.

## Decision ownership and instruction delivery (0.2.50)

Current readiness-policy requests distinguish permission to start bounded work from
acceptance of finished work. Planner/reviewer contracts and worker execution context
receive the same `decision_boundary`: the program owns mechanical admission, the
engineer reversible implementation, the reviewer semantic correctness, the user
consequential business scope, the governor scheduling and the arbiter recovery proposals.
Equivalent outcome coverage is sufficient. A declared substitute may support current
development against an unfinished dependency; it does not prove later real integration.
Required current prerequisites, authentication and native policy remain binding.

`readiness.py` owns prerequisite wording for planning, review and assignments;
`assignments.py` states local engineering discretion and observed-pattern reuse.
The graph still enforces the same readiness prefix, accepted contracts, frozen tests,
execution evidence, source freshness, human approvals and finite recovery budgets.
Legacy plan/roadmap identities and checkpoint decoding remain unchanged.

New provider-bound context receipts retain the exact call, role, operation, UTC capture
time and SHA256 of the assembled graph request. No request/response text is retained.
This is a graph-boundary fingerprint, not a claim about final native wire encoding or
model comprehension. Historical and node-only receipts remain valid and explicitly
unbound; no call linkage is inferred from their positions. Retry attempts receive their
own call bindings. These receipts do not grant execution or verification authority.

## Scoped setup and non-text baselines (0.2.49)

Baseline capture retains exact byte hashes for non-UTF-8 files using an explicit
`non-text` representation without invented text. Existing text entries are unchanged.
Unchanged non-text files do not enter the feature diff. Added, changed, deleted or
representation-changing non-text content stops finished approval with
`FINAL_REVIEW_NON_TEXT_UNSUPPORTED`; a supported content-review path is required.
Read failures and concurrent changes still fail capture without publishing a partial baseline.

Supported .NET proof discovery resolves project references and the explicit project
arguments of restore, build and test commands before inventorying their source roots.
It includes applicable ancestor configuration, declared targets and generated inputs.
All roots share the existing byte and traversal budgets. `dotnet_project_closure_v2`
distinguishes this method from historical receipts, which require fresh verification.
Unknown command flags, conditional topology and unsupported imports retain bounded
workspace fallback with runtime-mutable proof; an incomplete inventory is a failure,
never an empty successful receipt. Project metadata changing during discovery cannot
produce a narrow receipt. These checks do not authorize command execution.

If arbiter setup fails, its diagnostic retains a finite `initiating_failure` reference
(catalog code and graph stage) alongside the secondary failure. No model receives
invented source hashes, and no failed checkpoint is rewritten by installation.

## One format challenge at proposal boundaries (0.2.48)

Initial roadmap/planning, intake drafts, roadmap/plan reviews, arbiter decisions,
investigation advice and finished-content reviews receive one format-only correction
after a trusted structured JSON/schema rejection. A second invalid response stops.
Feedback contains finite diagnostic fields, never rejected provider text. Intake
charges the correction to its existing cumulative draft budget. Reviews preserve
the candidate, content hashes and logical review count; arbiter correction retains
the original failed-worker evidence binding. Native execution, permissions, human
approval, inspection and targeted revision budgets retain their existing controls.

## Arbiter chat message contract (0.2.47)

The arbiter sends its structured incident as a user message and appends the normal
shared-context message. This matches the chat adapters' message-list contract;
passing a bare incident dictionary fails before the native model is invoked.
Recovery tests now cross the real graph-node/chat-adapter boundary using an inert
native child, in addition to classifier doubles and live contract probes.

## Native tool failures reach bounded arbiter recovery (0.2.46)

A failed MCP operation in an otherwise fully validated, completed native worker
stream reports `CODEX_TOOL_FAILED`, never successful worker evidence. The parser
validates the entire stream and retains observed file changes before reporting
that failure. Invalid JSON, lifecycle, paths, incomplete streams and review-only
tool operations keep their existing rejection behavior.

The arbiter may choose verification of partial work only when the failed worker,
accepted plan, task, phase, run and current source hashes match. Its own recorded
classification call does not invalidate that binding; unrelated later calls do.
Only already accepted verification commands run. A failed proof uses the existing
investigator and bounded repair path. Stop remains available. No plugin/security
settings, permission controls, task approval or recovery budgets are relaxed.

An already approved requirements artifact may start a new monitored delivery with
`--story approved-requirements.md --finalize`. This preserves the supplied artifact
as task input, autonomous review/recovery and finalization without repeating intake.
Use this only with actual prior approval; retain its exact hash and provenance.

## Bounded requirements proposal correction (0.2.45)

An otherwise parsed requirements proposal can still violate retained-source,
stable requirement-ID or rendered document-size rules. Those proposals now receive
finite correction guidance within the same intake turn. Each synthesis consumes
the existing cumulative four-draft allowance; rejected proposals do not become
revisions, observations, human answers or approved documents. Finite rejection
reasons persist separately, without rejected text or arbitrary source references.
Exhaustion reports `REQUIREMENTS_DRAFT_REJECTED` and preserves the last valid draft.
Human exact-hash approval remains mandatory.

## Live intake and pre-roadmap recovery repairs (0.2.44)

Use `--requirements-file analysis.md` to enter human requirements grooming. The
legacy prompt and `--story` entry points preserve their existing route. The CLI
prints a JSON draft and pauses; resume with a workspace-relative UTF-8
`--feedback-file` to revise it, or `--approve-requirements EXACT_SHA256` to approve
the current document. Explicitly name any accepted bounded consequential
limitations. There is no conversational feedback form yet.

Missing intake files return bounded unavailable-source feedback rather than
aborting drafting. Actual successful reads alone establish observed hashes;
permission, boundary and size failures remain guarded. An arbiter handling a
recorded roadmap-stage failure can classify it before roadmap acceptance, while
worker/prover execution still requires the accepted contracts.

Read-only native turns now disable general plugins as well as remote plugins and
inherited project-document loading. Saved login and read-only sandboxing remain,
and a turn containing a native tool event is still rejected. Configuration intent
alone is not a proof that the native client advertises no tools.

## Requirements and delivery enhancements (0.2.43)

`--requirements-file analysis.md` performs bounded read-only investigation, drafts
the packaged Requirements document and waits for exact human approval. Feedback and
consequential bounded limitations survive resume. Material planning changes return
to that boundary. Automatic implementation review never supplies human approval.

Autonomous requirements runs include reviewed scoped polish/documentation and separate
finished-content review. A new autonomous prompt/story run can opt in with `--finalize`.
Legacy routes and saved policies remain compatible. Functional completion and PR
readiness are reported separately; missing quality evidence prevents readiness.

The common baseline, coherent assignment handoff, conservative project proof scopes,
backend-only status/accounting endpoints and installed-metadata marker are documented
in [the delivery operator guide](../docs/delivery-enhancements.md). Runtime replacement
must wait for active executions to finish. Source tests do not certify live providers,
production identity, native hook trust or general unattended reliability.

## Shared phase context size (0.2.40)

Integrity-policy-2 planning, review and execution prompts reference phase artifacts in the same request's validated canonical shared context. Full source values, prior plans, shared contracts, digests and observation availability remain present. This removes duplicate phase projections without truncating them. Legacy payloads keep their full projections. Native Codex requests use compact JSON and reject input exceeding the observed 1,048,576-character limit before dispatch. This does not automatically resume or alter saved runs.

## Sequential governor (0.2.36)

Fresh autonomous runs use governance policy 2. The solution architect identifies executables, repositories and dependencies, binds work pieces to those executables, records initial shared contracts and localized questions with working assumptions, and defines integration before execution. Each piece retains its plan versions, review findings/counters, accepted contract versions and actual verification evidence in its own checkpoint record. Routine engineering decisions remain with the coder.

The governor is deterministic and schedules one eligible piece at a time. It continues independent work around a blocked piece, then restores that piece's plan/findings for explicit user feedback when no other work is ready. This adds no model, approval gate, parallel writer, or automatic resume of a saved feature run. The existing four model roles remain `gpt-6.1-sol`.

Only a solution-architect piece plan may propose `contract_changes` with an existing ID, current `base_version`, new `definition` and reason. Independent plan review accepts the plan and changes together. The engine advances versions, preserves old evidence, invalidates completed participants and dependent work, and schedules their new plan/review/verification cycles before final integration. Reopened pieces may update tests frozen for superseded contracts; unrelated completed tests remain frozen. The first version keeps contract participants and the decomposition fixed; a changed ownership graph requires a fresh run. At most 32 accepted contract edits and the existing 400 graph steps bound a fresh run.

Model requests include current contract definitions and each piece's latest plan, review decisions and evidence references. Full historical plan bodies remain in the saved checkpoint instead of being repeated into every request. Older checkpoints keep governance policy 1 and their existing accepted hashes and execution behavior.

## Single-model baseline (0.2.35)

New runs default every role—orchestrator, coder, investigator, and independent reviewer—to `gpt-6.1-sol` through Codex CLI using the existing ChatGPT login. No Gemini installation/login or API key is required for the standard run. Planning, inspection, investigation, and review use isolated ephemeral read-only native turns with native tools disabled; only coding uses the existing approved workspace editing path. Graph tool requests and structured synthesis use native JSON with strict local validation, preserving unencoded edit values and graph-owned tool dispatch. Review retains its existing native decision schema.

Roadmap review checks semantic outcome coverage and phase ownership while leaving routine fixture, cleanup, helper, and test-case details to the coder. Phase plans retain executable scope and verification contracts. Known, already-closed finding IDs may be re-acknowledged harmlessly; unknown IDs, contradictory decisions, reopened resolved IDs, silent omission of active IDs, and acceptance with open findings remain invalid. Old closure acknowledgements do not count as new progress. Attempt bounds and execution proof are unchanged.

Existing saved mixed-provider configurations remain readable, and legacy transports are retained for compatibility. Multi-model runs are deferred as a future enhancement. Installing this baseline does not resume or migrate saved work; start a fresh run to use the new defaults.

## Targeted revision values (0.2.34)

Roadmap, plan, and strategy revisions supply each edit's required `value` as native JSON, rather than escaped JSON inside `value_json`. Strings stay literal strings; inserted phase/task objects and command arrays are ordinary JSON objects/arrays. Removal uses `"value": null`. Saved legacy edit dictionaries remain readable at the application boundary. Run/base identity, active findings, atomicity, untouched content, list-index semantics, owned fields, and existing attempt bounds remain enforced. Each value is limited to finite JSON, 32 levels, and 65536 UTF-8 bytes; the combined value limit is 524288 bytes.

Schema rejections expose a fixed reason and bounded field/index path, such as `edits[1].value`, plus corrective guidance. Parser rejections retain finite numeric locations. Rejected values, unknown field names, exception bodies, and raw model responses are not added to diagnostics. A rejected-edit budget ends with `REVISION_CONTRACT_EXHAUSTED`, distinct from semantic review exhaustion; terminal output labels the retained findings as belonging to the last completed review. A corrected candidate still needs independent review before execution. This update does not start, resume, migrate, or clear any feature run.

The standalone engine uses native LangGraph, durable SQLite checkpoints, and autonomous Council plan review by default. A separate Codex reviewer accepts the proposed plan or requests bounded revisions before coding. Successful execution and validation finish without routine human approval; unresolved planning blockers checkpoint for feedback. Engine file tools and command working directories are bound to the selected workspace. The native Codex coding worker additionally uses its own workspace-write sandbox and approval review. Subprocesses retain the launching user's operating-system permissions; this engine is not an operating-system sandbox. Missing credentials, missing validation, and failed tasks return errors.

Install the complete Council distribution with its `setup-council.ps1` script. It requires Windows, PowerShell 7+, Node.js 20+, Python 3.11+, and access to the Python package index. The script creates a private Python environment under the installed Council's `runtime/` and installs this package. The wheel's `council` entry point and `python -m council` use the same CLI. Runtime files and credentials are not part of the share source.

Run Python directly from PowerShell, from any directory. Activation is unnecessary because the executable explicitly selects the private environment:

```powershell
$python = "$env:USERPROFILE\.council\runtime\Scripts\python.exe"
$workspace = "$env:USERPROFILE\workspace_root"
& $python -I -m council --doctor --workspace $workspace
& $python -I -m council --workspace $workspace 'Implement the approved feature'
```

Use `--dry-run` to generate a preflight-validated single plan without review or execution. New runs default to `--approval-mode autonomous`. Use `--approval-mode manual` to request human plan/final gates, or `--auto-approve` to explicitly bypass engine review. These options are mutually exclusive and separate from native Codex permissions. `--no-input` suppresses manual prompts; autonomous review still proceeds. `--resume <run-id>` preserves the recorded policy and workspace.

New autonomous runs use one story and one command with a reviewed roadmap of one to eight sequential phases. Council plans, reviews, executes, and verifies at most 12 tasks for the current phase before planning the next one. The reviewer checks the roadmap first, then each phase against its goal and actual completed-phase evidence. A phase cannot demand a passing test for a later endpoint or screen as readiness. Each completed phase stores its accepted plan digest, verified task IDs, test-result count, and changed-file inventory in the SQLite checkpoint. A later blocker preserves completed phase evidence and `--resume` continues the blocked phase without replaying earlier workers. The final gate requires every phase to complete. Existing single-plan checkpoints retain their recorded policy and graph route.

Roadmap inspection is limited to four read-only rounds. Phase inspection uses at most four rounds per phase and 32 rounds total for the run. Roadmap review gets four attempts and three revisions; phase review gets four attempts and three revisions, with one bounded strategy reset allowing two further reviews and one correction. An unresolved business decision or exhausted budget checkpoints as a blocker for feedback. JSON includes the roadmap, current phase, completed phases, and counters; the human blocker summary shows only open findings.

Interactive task runs and resumes open the local Council viewer when Deno and the packaged viewer assets are available. The URL is printed on stderr; the page follows sanitized diagnostic events and shows a read-only SQLite checkpoint count. Use `--no-viewer` to skip it. Doctor, dry runs, and noninteractive commands do not open the viewer. Viewer startup failure does not stop the Council run. The viewer remains available for ten minutes after the CLI exits, then closes its loopback server.

Interactive terminals show a yellow "COUNCIL BLOCKED" or red "COUNCIL ERROR" cue immediately before the final result. A blocker also prints a wrapped `Open issues` section on stderr, filtering resolved entries from the finding ledger and including the current finite verification-preflight reason/guidance when present, followed by a `Full JSON (copy/paste)` label. A preflight rejection is visible even when no model review findings exist. Operational failures label those findings as coming from the last completed review and show the interruption diagnostic first. The complete result remains one unmodified JSON object on stdout, including resolved ledger entries for triage and replay. Redirected output gets no human cue or summary; setting `NO_COLOR` keeps the interactive section plain.

Codex JSONL parsing uses only LF as an event boundary. Valid Unicode line separators inside event strings remain part of their JSON value; malformed physical JSON lines still fail closed. A transport failure after native file edits remains terminal and requires review of the working tree.

Native Codex CLI 0.164.0 emits a flattened web-search provider ID after the native item ID, duplicating `item.id`. The event decoder recognizes only that version and shape: a web-search item lifecycle record with exactly two distinct valid IDs, the native `item_<counter>` ID first. Lifecycle tracking retains the native ID and reports a finite `cli_web_search_id_compatibility_count`. Other duplicate keys, nested duplicates, unsupported versions and malformed identifiers remain rejected. Substantive review/plan JSON decoding stays strict; completion, file boundaries and review-only tool restrictions still apply. This compatibility rule adds no automatic worker retry or checkpoint resume.

Piece-completion history is projected only after the phase-completion node reaches its successful governor transition. If a final freshness check raises, the piece stays open and no successful completion entry is added. Failure diagnostics and observed work remain available. Installing this correction does not rewrite historical failed checkpoints, refresh stale verification records or automatically resume a run.

## Autonomous review and convergence (0.2.9)

The designated Council reviewer and tool-free planner revision calls receive the requirement, plan, inspection summary, observed inspection receipts, the same applicable Council/project specialist guidance, prior findings, and explicit recovery feedback. Receipts retain tool identity/arguments and observed results in private checkpoints, capped at 64 records, 16 KiB per record and 128 KiB total UTF-8. Availability and truncation are explicit; old runs do not invent missing evidence. Receipts are source context, not instructions, and never appear in general diagnostic logs. This is an independent model invocation applying specialist guidance, not a claim that every Council specialist voted. Model review does not independently prove repository facts or command safety.

Structured decisions are `accept`, `revise`, or `escalate`. New autonomous runs record review protocol 2. Findings carry stable IDs, descriptions and technical/user-decision classifications. Every unresolved ID must be explicitly retained or closed by the reviewer; silent omission, duplicate IDs and reuse of resolved IDs reject the decision. Escalation requires a concrete user-decision finding. Optional improvements should not block acceptance.

Protocol 2 normally permits six reviews/five revisions per explicit recovery attempt. After two consecutive revised-plan reviews without progress, or after the ordinary budget is exhausted with technical findings still open, one architect strategy reset may reconsider circular prerequisites and task structure using the existing evidence and ledger. The reset counts as a revision and allows at most two additional reviews and one ordinary correction (eight reviews/seven revisions total in the initial attempt). It neither invents missing business facts nor approves its own proposal: deterministic preflight and the independent reviewer still gate execution. User-decision escalations and operational failures do not trigger it. A failed post-reset review still blocks, and explicit human feedback starts a new ordinary recovery budget without another automatic reset. Progress requires both a changed plan digest and reviewer-confirmed closure of a previous finding; rewording alone does not qualify. New findings cannot reset limits. Acceptance requires no unresolved findings and binds coding admission to the exact plan contract, excluding execution statuses. Existing checkpoints lacking protocol 2 retain the original three-review/two-revision policy, including after feedback; upgrading does not migrate them automatically.

Unresolved findings, invalid decisions, provider failures, and invalid revisions produce a durable `PLAN_REVIEW_BLOCKED` interrupt. CLI stdout reports `status: BLOCKED`, diagnostic, findings/ledger, counters, protocol/limits, evidence availability, run ID, and next action; exit code is 2. `blocker_kind` distinguishes `user_decision`, `stalled`, `budget_exhausted`, and `operational_failure`. The fixed stalled diagnostic is `PLAN_REVIEW_STALLED`. It never reads stdin for autonomous decisions. Resolve the reported issue, save feedback to a workspace-relative UTF-8 file, then resume:

Read-only model calls share one graph-owned retry policy. `CLI_TIMEOUT`, `CLI_EXECUTION_FAILED`, `CLI_IO_FAILED`, and `CLI_START_FAILED` receive one retry with the same request and model. Each attempt has its own call receipt; retry operations end in `_transport_retry`. This applies to roadmap/phase inspection, synthesis, review, revision, strategy reset, and investigation. A second failure propagates through the existing failure or blocker boundary. Authentication, quota, model/argument errors, output limits, and invalid responses do not trigger transport replay. Native coding turns are not replayed automatically because they may have changed files. Review and revision allowances are unchanged; adapter retries do not nest beneath the graph policy.

```powershell
& $python -I -m council --workspace $workspace --resume '<run-id>' --feedback-file 'temp\review-feedback.txt'
```

Feedback must contain 1-12000 characters (file at most 48000 bytes). It starts a recorded recovery attempt, revises the plan, and obtains fresh review. Cumulative counters remain; per-attempt baselines, ledger and progress streak restart only with explicit feedback. Original inspection receipts remain available. Previous attempt records remain in checkpoint history. An ordinary resume or boolean approval cannot reset budgets or approve a blocker. Terminal historical failures are preserved; no failed-plan import or worker replay is added. Initial planning failures retain existing terminal behavior. Crash replay can repeat an in-flight external call; the configured budgets bound completed graph attempts, not lifetime billing across crashes.

Invalid reviewer decisions retain `PLAN_REVIEW_INVALID` and add optional `review_decision` detail: a finite `reason`, validation `stage` (`response`, `schema`, or `ledger`), allowlisted `field`, and nullable one-based bounded `index`. Reasons distinguish response type/size, JSON, schema shape/type/bounds, duplicate IDs, decision/escalation inconsistencies, missing active IDs, invalid closures, reopened resolved IDs and ledger capacity. Only the first detected rejection is reported; it does not enumerate every issue. Ledger validation finishes before ledger/progress mutation. The graph emits `plan_review_rejected` with the same sanitized detail before blocking; checkpoints and blocked output preserve it. Malformed optional detail is ignored at loading/output boundaries, and legacy diagnostics without detail remain compatible. No rejected text, arbitrary keys, Pydantic input/context/messages or raw responses are retained. This adds neither retries nor budget changes and cannot reconstruct an earlier discarded reviewer decision. Reviewer transport success still means the native call completed; the separate rejection event identifies local decision failure.

The native review operation uses an empty private working directory, `--ignore-user-config`, a read-only sandbox, disabled shell, collaboration, app and remote-plugin features, disabled web search, and an empty MCP configuration. It receives no engine tools and rejects tool-operation events. It keeps the existing ChatGPT login without copying credentials. Native managed restrictions still apply. This review-only invocation is covered by inert CLI tests; live provider reliability is not certified. See the [official configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) for the shell feature setting.

Execution keeps the existing verification commands, bounded repair loop, and workspace audit. When they pass, autonomous mode completes without a final human gate. Execution failures remain failures with evidence; this change does not add automatic replay of partially executed workers. Unperformed pre-submit phases remain explicitly unverified. No automatic commit, push, merge, publication, or deployment is added.

New autonomous checkpoints use configuration v4 with a separately pinned `reviewer` role. Manual/bypass new runs retain v3. Existing v1-v3 checkpoints and absent policy fields retain their original manual/bypass behavior; upgrading does not silently approve saved work.

To read development instructions from a file, use a workspace-relative story path:

```powershell
& $python -I -m council --workspace $workspace --story 'temp\.todo\ai_orchestration\validation_feature.md'
```

## TDD verification phases (0.2.11)

Verification plans cannot override startup execution policy on direct PowerShell/pwsh argv. Preflight returns `PLAN_VERIFICATION_INVALID` with finite reason `EXECUTION_POLICY_OVERRIDE` and command index. Worker admission rechecks saved accepted tasks without rewriting their plans/digests; the subprocess runner independently raises `VERIFICATION_POLICY_OVERRIDE` before process creation. Detection covers case-insensitive executable basenames/full paths, ExecutionPolicy prefixes and ep alias, including colon/equal forms. Startup scanning ends at -File, so subsequent script arguments remain literal. Use ordinary trusted -NoProfile -File invocations and report native policy limitations. This is a narrow direct-argv check, not a shell sandbox, script-content analyzer or guarantee against arbitrary indirect commands; native restrictions and the instruction against weakening security remain in force. Review/revision budgets are unchanged.

Read-only planning handles explicitly engine-defined path denials as unavailable evidence: absolute/parent/outside paths, private/generated exclusions and links/junctions remain rejected. A typed PermissionError is converted to fixed tool feedback only for the three offered inspection read/list/search tools. The existing inspection round limit is unchanged; no alternate access or extra retry is attempted. History marks the operation unsuccessful, durable receipts omit rejected arguments, and `inspection_read_rejected` reports only an allowlisted `boundary_reason`. Native OS PermissionError, unknown/forged errors, non-read tools and coding-path denials remain terminal. Unavailable sources must not be presented as observed facts. Older generic permission failures cannot reveal the discarded target/reason.

Since 0.2.16, new verification results identify the one-based `command_index`. Rejected red results retain `RED_EXPECTATION_NOT_MET` (or the existing frozen-source reason) and add optional sanitized `verification_detail`. Its finite reason distinguishes invalid reports, exit-code mismatch, empty/duplicate expectations, missing expected cases, expected cases that passed, unexpected failures, assertion type/header/body mismatch and frozen-source changes. Counts are bounded; `missing_expected`, `passed_expected` and `assertion_index` reference the accepted expectations filtered to that command, in their original order. They never contain observed test names, report text or assertion bodies. The primary reason is not an exhaustive diagnosis. A `verification_rejected` event carries the same safe facts and one-based task/command indices. Malformed optional fields are ignored at loading/output boundaries; legacy results without them remain readable.

The existing investigator and coding worker receive fixed correction guidance and affected expectations resolved privately from the accepted contract. A missing test must be implemented through the required real harness; omitting tests, unconditional throws, weakening assertions or implementing later green work cannot satisfy red. An unsupported harness must be identified as a blocker. This adds no automatic replanning, extra retries or relaxed acceptance. Red evidence is still recorded atomically for the whole task: one successful red command is not accepted/frozen independently if another command fails. Historical aggregate results cannot reconstruct discarded reports or model diagnoses; this feedback improves future repairs without guaranteeing model convergence.

Tasks default to `verification_phase: green`, preserving exit-zero behavior and historical checkpoint acceptance hashes. The engine never infers an expected failure from prose. An explicit `red` test-writing task must declare a later green implementation task and the exact expected assertion failures for every verification command:

```json
{
  "verification_phase": "red",
  "red_verification": {
    "implementation_task_id": "implement-validation",
    "expected_failures": [{
      "command_index": 1,
      "test_name": "blank Standard is invalid",
      "assertion_message": "TDD_RED: blank Standard validation is missing"
    }]
  },
  "test_commands": [["deno", "test", "--reporter=junit", "tests/validation.test.ts"]]
}
```

Initial red-phase support is Deno JUnit on stdout, verified locally against Deno 2.9.5. Each command targets one declared `.test.ts` or `_test.ts` file. Tests must compile and load; new interfaces/harness may need a preceding green preparation task. Red reports must be complete and internally consistent, with positive executed test counts, no errors/skips/disabled tests, unique names and exactly the declared failures. Each failure must report an `AssertionError` matching the declared `TDD_RED:` signature. Missing imports, type-check failures, runtime errors, malformed/empty reports, unknown failures, non-1 exits and unexpectedly passing tests do not establish red. Reporter redirection, skipped type checks, filtering, retry/watch/no-run and other execution shortcuts are rejected by preflight. Report parsing is capped at 1 MiB/256 cases per command.

The named later green task must rerun each exact red argv in the same working directory. Red tasks declare at most 32 test sources and 16 commands; a plan has at most 64 red commands. Once red is confirmed, the engine hashes those declared test files (maximum 256 KiB each), records the executed case names and advances without spending repair retries. Later tasks cannot declare edits to those frozen files. Green must show a complete error-free zero-failure JUnit rerun containing all prior cases and unchanged source hashes. Removed, skipped or rewritten tests cannot close the obligation. Final audit rejects open obligations or changed frozen sources. Genuine red harness failures still use the existing bounded repair behavior.

Test results preserve facts: an accepted red result has `passed: false`, `exit_code: 1`, `verification_phase: red`, `expectation_met: true` and `verification_reason: EXPECTED_RED_CONFIRMED`. `red_phase_evidence` records hashes/case identities and whether the later green transition closed. Raw JUnit/stack traces are not persisted in those records. Reporter evidence and test-source freezing do not prove test semantics or prevent a malicious process from fabricating output; model review and normal regression remain necessary. Other runners retain green verification. Existing failed runs are not revived or rewritten.

## Specialist identifiers and plan preflight (0.2.7)

### Planning guidance and deadlines (0.2.14)

Review and revision requests include each resolved guidance source once, in first-encounter order, while retaining every required specialist package. Distinct paths with identical contents remain distinct sources. Deduplication affects output only: each file is still read and checked against its 64 KiB limit, each specialist assembly against its 192 KiB limit, and combined review guidance against its 768 KiB limit. No receipts, findings, plan fields or private-path restrictions are removed. Each request starts with a fresh source set.

New Gemini CLI settings snapshots use `timeout_policy_version: 3`, `timeout_seconds: 600`, and `structured_timeout_seconds: 600`. Inspection, format correction, investigation and structured synthesis all receive the same finite deadline. Policy 2 snapshots retain their original 180-second inspection/600-second synthesis deadlines; legacy snapshots without policy fields retain 180 seconds. Historical model settings are not migrated. Codex deadlines remain 600 seconds.

Gemini model-call evidence records `effective_timeout_seconds` on success and failure alongside the unchanged settings snapshot, including roadmap and strategy-reset synthesis and transport retries. The transport receives a separate deadline copy. Timeout and I/O diagnostics preserve bounded process exit status, stdout/stderr byte counts, stderr hash and fixed signal categories. Raw provider output remains excluded. Cleanup may add time after the deadline. Read-only timeout retry follows the shared policy above.

### Engine resilience (0.2.27)

Defaults are `gpt-6.1-sol` through Codex CLI for every role. Planning receives observed host executable availability instead of assuming PowerShell 7 or other tools are installed. Availability still requires real permission, authentication and service probes.

Every green task with no edit targets runs its declared verification commands directly, without a coding session or source inventory. Native edit tasks in a multi-repository workspace must use a narrower working directory. Verification subprocesses have a finite 600-second default, terminate their process tree on Windows timeout, and retain partial output for the existing bounded investigator context.

Roadmap inspection now has the same one-attempt malformed-JSON correction as phase and revision inspection. Closed red-test evidence is archived through phase transitions and survives checkpoint reloads. Later phase plans cannot target those frozen files, and workers, provers, phase completion and final audit continue checking their hashes. New fields default to empty for old checkpoints; missing historical evidence cannot be reconstructed by upgrading.

### Architecture context lineage (0.2.28)

The roadmap reviewer receives captured source receipts and their availability/truncation flags. On acceptance, those bounded receipts are copied into dedicated roadmap-inspection state. Phase inspection still resets its own receipts; it cannot erase the preserved roadmap observations. Historical checkpoints without the new receipt fields explicitly report that evidence unavailable.

Phase planning, review, revision, strategy reset and coding receive the complete approved roadmap, its accepted digest, roadmap observations, current phase and completed phase summaries. The projection checks the accepted digest before exposing the blueprint and leaves state unchanged. Workers also receive the current accepted plan's architecture summary. The approved global blueprint supplies intent and contracts; execution scope remains the current phase/task. Reviewers distinguish missing evidence from a missing current-phase deliverable and request concrete technical corrections for the latter.

The graph remains sequential. Nodes return complete validated state snapshots; adding list-append reducers to those channels would duplicate existing entries. Parallel dispatch requires separate task state, deterministic merging, dependency scheduling and filesystem isolation; it is not enabled by this context repair.

### Gemini JSON generation contract (0.2.29)

Gemini CLI `--output-format json` wraps the final model answer as a string; it does not constrain that inner answer to JSON. For tool envelopes and structured synthesis, Council now configures the documented `modelConfigs.overrides` generation setting `responseMimeType: application/json` in the isolated per-call project settings. The override matches the exact selected model; an empty match is ignored by the native configuration service. The isolation probe verifies that the effective settings retain this contract along with the existing tool/hook restrictions. Plain investigation responses remain text. No global CLI settings or installed CLI files are modified.

The existing strict JSON parser, duplicate/nonfinite rejection, schema validation, offered-tool checks, path boundaries and single format-correction limit remain. Invalid output includes a finite `response_json` diagnostic: reason, response byte count and parser line/column/position when known. Reasons distinguish empty responses, Markdown fences, invalid escapes/control characters, unterminated strings, trailing data, duplicate keys, nonfinite numbers and invalid encoding. Diagnostics retain no rejected content or field names. Each format correction receives only these safe facts and fixed reason-specific guidance. Historical generic JSON failures cannot be reconstructed.

### Gemini inspection response contract (0.2.30)

Read-only Gemini inspection also supplies `responseJsonSchema` in the same isolated settings. The small schema constrains the response envelope and exact offered tool-name enum, and describes a flat union of argument properties. The live OAuth service rejected a nested per-tool schema; the flat form passed three successive synthetic inspection responses. The isolation probe compares the effective schema with the requested schema exactly. This uses the native JSON Schema generation setting documented by [Google](https://ai.google.dev/gemini-api/docs/generate-content/structured-output?hl=en); local validation remains authoritative. Non-read bindings and future incompatible argument-property unions retain ordinary JSON generation.

Roadmap, phase and revision inspections share one correction path for malformed JSON, tool envelopes/calls, unoffered names and non-object arguments. Correction supplies only the recognized diagnostic code, fixed guidance and the actual offered names; rejected content is never replayed. The entire batch must pass validation before any request is dispatched. A second rejection is terminal. Existing `*_format_retry` operation identities and inspection budgets remain unchanged. Transport/auth/quota failures, native-tool safety failures, structured synthesis and tool execution do not enter this response-correction path.

### Shared graph information integrity (0.2.33)

New autonomous runs record `graph_integrity_policy_version: 2`. Each fresh invocation still creates a new run ID and empty orchestration state. Historical checkpoints are read only through an explicit resume; older runs retain policy 1 and their original review/revision behavior.

The initial planner creates a complete roadmap or phase plan. Later roadmap revisions, phase-plan revisions, and strategy resets return a bounded `DocumentRevision` with the current run ID, document kind, base digest, and at most 64 finding-linked edits. Paths address stable phase/task IDs and individual clauses or scalar fields. Explicit phase/task insertion and removal support structural correction; unrestricted document, object, and list replacement is rejected. List indices refer to the original base. The engine applies a complete batch atomically to a copy, preserves all untouched content, and runs normal roadmap validation or plan preflight before review. Rejected proposals leave the prior base intact and receive finite corrective feedback within the existing revision allowance.

Active review finding IDs justify edits; `U1` references recorded user feedback, and `V1` references deterministic preflight correction. Only a specific preflight status correction may reset an invalid initial task status to pending. A model cannot mark a task completed through revision. Roadmap review now uses stable protocol-two findings and explicit closure accounting, like phase review. Closed findings remain traceable; actual regressions require a new finding. Roadmap review covers outcomes, ownership, and dependencies, while exact file targets and executable commands belong to the owning phase plan.

All model boundaries use shared canonical context containing the original requirement, applicable feedback, draft/accepted versions, phase/task scope, findings, bounded observations, and relevant execution or repair records. A manifest names each delivered value's digest, producer, and availability. The engine validates the actual outbound content against current state before invoking a provider and stores manifest receipts in private checkpoints. A reference without content does not satisfy delivery. Missing/truncated source observations remain explicit; summaries do not replace the source requirement. Workers receive only the applicable task view plus higher-level contracts and observations, rather than a replacement conversation history.

The wrapper seals run identity, requirement and policy/model settings, validates node ownership of shared fields, and prevents rewriting accumulated call/test/phase history. Worker/prover progress changes do not alter accepted contract digests. A rejected internal mutation restores the previous semantic state while retaining actual call and file-change observations. The sequential graph continues to return complete snapshots; no append reducers are applied to those snapshots.

Actual verification adds uniquely identified records bound to run, phase, task, graph step/attempt, accepted plan, and command digest. Source fingerprints cover declared targets and existing workspace-relative command files; they are not a complete transitive dependency graph. Implementation verification also checks that these inputs stayed unchanged during the command; an exit-zero command that changes them cannot certify the changed source. Readiness/setup probes may intentionally produce their qualified prerequisites. Phase completion and final-plan audit require matching successful evidence with current fingerprints in that declared scope. Completed earlier phases remain historical proof; later implementation does not turn their earlier results into current final-layer proof. Record identities prevent duplicate recording at the same graph step; they do not promise exactly-once external command execution after a crash.

New-policy investigators return bounded `RepairAdvice` linked to the specific failed command, even when a later command succeeded. Retained advice contains finite categories/actions, declared target references, and explicit limitations. It survives checkpoint reload and is cleared after successful repair. Arbitrary model prose, credentials, customer data, and raw process output are not persisted as repair advice. If transient output is unavailable after restart, that limitation is recorded. Advice remains a hypothesis and cannot change an accepted command or count as a passing test.

These controls protect preservation, version identity, ownership, and delivery. Independent review and actual execution still establish semantic correctness and feature behavior. Synthetic transport/lifecycle verification does not prove completion of the application story.

### Graph contract alignment (0.2.32)

Initial plans, revisions, strategy resets and review preflight use one `validate_proposal` policy. Autonomous protocol-2 initial proposals receive the same bounded correction for invalid targets, working directories, argv/TDD/readiness contracts and specialist identifiers as later revisions. Non-pending statuses follow readiness validation in every current-policy proposal stage. Manual and legacy rejection behavior remains; catalog/package/access failures are not converted into approval. Rejected initial paths and specialists remain correction data and cannot select instruction sources. Every corrected proposal still needs preflight and fresh independent review.

Roadmap synthesis/revisions and review share the same bounded inspection receipts and availability flags. Roadmap recovery guidance remains visible to review and subsequent phase planning, coding and investigation as task data; it cannot expand an accepted task's authority. A shared phase-start reset prevents roadmap recovery counters leaking into the first phase and preserves unarchived frozen evidence. Phase completion archives that evidence before resetting local state.

All original roadmap, phase and revision inspection responses consume the shared 32-round budget before invocation. Format corrections and transport retries remain within the same round. Older checkpoints use the greater of their stored counter and exact original inspection call records, capped at the existing limit, so undercounted history cannot grant extra rounds. Exhaustion permits tool-free synthesis with missing inspection evidence explicit. Legacy whole-plan round policy is unchanged.

Worker and investigator receive the same accepted task, plan architecture/digest and current roadmap/phase context. The dispatcher validates the complete tool-call envelope, names, unique IDs and available argument schemas before executing a valid prefix, regardless of provider. The Gemini adapter validates registered tool argument schemas before returning a response, so missing required fields and wrong types use the existing bounded inspection correction. Runtime tool failures can still stop a partially executed valid batch; side effects are not transactional. Final audit checks both current and archived red evidence for closure and unchanged frozen files. Interactive blocker summaries now show every repairable preflight code using finite guidance, with unchanged full JSON.

These contracts are tested through an eight-phase fixture journey, including reused task IDs, prerequisite-only setup, a late verification repair, the 32-round cap and final tool-free planning. Fixtures exercise the real graph, SQLite checkpoints, tools and subprocess verification with synthetic providers; they do not certify the real application feature E2E.

### Specific verification feedback (0.2.13)

`PLAN_VERIFICATION_INVALID` covers command shape and TDD contract failures. It now includes an optional `verification` object: a fixed `reason`, its actual `field`, and nullable one-based `command_index` and `related_task_index`. The enclosing `task_index` and these indices refer to the rejected candidate. For example, `FROZEN_TEST_TARGETED` identifies the red task and the later task proposing to edit its frozen tests; `GREEN_RERUN_MISSING` identifies the unmatched red command and its implementation task. Other reasons distinguish missing contracts, unsupported runner/flags, undeclared test sources, pair ordering/directories, expectation identities and size limits.

The planner receives the same detail plus fixed `verification_correction` guidance on the next revision. Console/file preflight events and `last_plan_validation` expose only the validated finite detail, without rejected command arguments, test names or paths. Invalid details are omitted at diagnostic boundaries and rejected when loading feedback state. Legacy feedback without the object remains readable. Installing this release cannot reconstruct reasons for historical rejected proposals that were not retained.

The shared plan contract includes a valid red/green task example. Red tasks target test sources only; production interfaces/harness must already compile or be prepared in an earlier green task. Green implementation and later verification/audit tasks rerun frozen tests without listing them as edit targets. Invalid candidates still leave the last valid plan intact, consume the same bounded revision allowance and require fresh review after correction. No validation rule, retry limit or acceptance gate is relaxed.

### Revision preflight recovery (0.2.10)

Initial planning, review and revision receive the same explicit plan contract. Target files are relative to the workspace root, including the project prefix, rather than relative to the task working directory. Native working directories are workspace-relative existing safe directories. External Council instruction files are read-only guidance; referencing a validation script does not make it an edit target. No rejected path is silently normalized or allowed through the boundary.

For protocol-2 revisions, a rejected target path, working directory, verification argv shape or unknown specialist identifier returns structured corrective feedback to another tool-free revision call. Every proposal consumes the existing five-revision allowance. Invalid candidates retain the previous valid plan and never reach review or workers. A corrected proposal must pass preflight and fresh model review before coding. Repeated invalid candidates stop at the existing limit with `PLAN_REVIEW_EXHAUSTED`; `last_plan_validation` identifies the safe code, one-based task/field positions and field name, while `plan_preflight_failure_count` reports the cumulative rejection count.

The latest rejected-field context is private checkpoint data: task ID (256 UTF-8 bytes), description (512 bytes), rejected path/specialist value (2 KiB) and truncation flag. Arbitrary verification arguments, full rejected proposals and raw responses/errors are not retained. The planner sees this bounded context on the next revision. General diagnostic events (`plan_preflight_rejected`) and public blocker summaries omit those private values. Successful correction clears the current feedback; earlier attempt checkpoints retain it. Explicit recovery feedback preserves useful last-validation context without granting acceptance.

Provider failures, malformed response/schema, unavailable/redirected specialist packages and catalog failures still block immediately. Initial-plan validation, dry-run and protocol-1 failures retain their existing semantics. Installing this repair does not resume or edit existing blocked runs; explicit feedback is still required to start a recorded recovery attempt.

Plans use canonical specialist package identifiers such as `the-coder`, drawn from the installed manifest's specialist catalog. The planner receives that catalog, and the schema description explicitly requests canonical identifiers. Exact known display call signs are also accepted at preflight: `[THE CODER]` maps to `the-coder`. Canonical identifiers remain unchanged. There is no fuzzy matching, case/whitespace cleanup, unknown-role fallback, or interpretation of identifiers as paths. Workflow packages outside the specialist catalog cannot be assigned as specialists.

Preflight validates a copy, checks package availability through the protected loader, and presents the normalized plan at Gate 1. Dry-run uses the same validation. The plan reviewed and checkpointed is the plan that dispatch uses. Missing or redirected packages are rejected. Existing working-directory, target-boundary, and explicit verification-argument requirements remain in force.

Known failures have fixed diagnostics: `PLAN_CATALOG_INVALID`, `PLAN_SPECIALIST_INVALID`, `PLAN_SPECIALIST_UNAVAILABLE`, `PLAN_VERIFICATION_INVALID`, `PLAN_WORKING_DIRECTORY_INVALID`, and `PLAN_TARGET_PATH_INVALID`. Task-level failures include a bounded numeric `task_index`; new diagnostic messages and events do not echo the rejected model value or path. Existing checkpoint plan contents remain private execution state, not sanitized diagnostic logs.

Historical failed checkpoints are not edited, resumed, or imported automatically. This validates assignment/preflight contracts and does not prove that model-generated task descriptions, verification commands, or factual assumptions are correct. Plan review is autonomous by default and manual only when explicitly selected or preserved from a legacy checkpoint.

## Bounded inspection and plan review (0.2.6)

Each inspection request includes its round number, the fixed twelve-round limit, and the allowance remaining after that round. Console events show `inspection_round_started` with bounded numeric round fields. Inspection offers only workspace read/discovery tools.

When the final allowed round still requests tools, the graph executes that round's valid read-only requests, emits `inspection_budget_reached`, and moves to the separate structured-plan call without offering more tools. Its request includes all collected results, including the last round, and instructs the planner to identify missing evidence and unresolved assumptions in `architecture_summary`. Natural completion can proceed earlier. Reaching the inspection budget is a normal handoff, rather than a generic execution failure. A failure of the plan-generation call still fails the run with its own diagnostic.

The checkpoint, approval details, pause results, and final results include optional `planning_inspection` metadata: `rounds_used`, `round_limit`, and `limit_reached`. The last flag means the budget forced a handoff; a model that naturally finishes on round twelve has `limit_reached: false`. Old checkpoints with no recorded inspection summary use `null` rather than inferred values. Gate 1 still requires review of scope, verification commands, assumptions, and evidence gaps before coding. Existing explicit `--auto-approve` behavior is unchanged. Prompt instructions request honest gap reporting but do not independently prove the model's factual claims.

The limit is twelve inspection rounds plus the structured-plan call, with the existing per-call timeouts and at most one response-contract correction per rejected inspection round. No inspection conversation is reconstructed for previously failed runs; start a new run. The new handoff is validated with synthetic responses, not a certification of live planning reliability.

## Planning inspection format recovery (0.2.5)

Tool inspection requires a strict JSON object with `content` and `tool_calls`; completion uses an empty `tool_calls` array. The CLI's `--output-format json` packages the CLI envelope and does not itself constrain the model's response string. The adapter explicitly requests both tool-call and completion formats.

During Gemini CLI planning inspection and read-only plan-revision inspection, a `GEMINI_RESPONSE_JSON_INVALID` failure receives at most one corrective attempt using the current in-memory conversation and fixed formatting feedback. Rejected output is never executed, extracted, stripped of fences, or retained in new logs. The corrective response must pass the same strict parser and tool validation. A second error terminates the run. Invalid tool requests, native CLI-envelope failures, permissions, timeouts, authentication/quota errors, structured-plan output, API transports, and coding calls do not receive this recovery.

The first failure remains in model-call evidence; its corrective call appears separately as `planning_format_retry` or `plan_revision_format_retry`, with its own sequence and duration. Each call keeps the existing 180-second timeout. Inspection remains bounded to 12 rounds, with at most one corrective call per malformed round (up to 24 inspection attempts total). Format recovery is distinct from verification repair and does not change approval gates or Codex behavior. It improves recovery from format violations but does not guarantee live planning reliability. Previously failed runs cannot resume their discarded in-memory inspection conversation; start a new run.

## Progress and safe diagnostics (0.2.4)

The CLI prints brief JSON lifecycle events on stderr: graph-node start/end, model-call start/success/failure, and durable interrupt waits. Autonomous planning interrupts emit `planning_blocked`; manual gates emit `approval_waiting`. Each event includes a run ID and elapsed seconds since this process started. There is no token streaming or heartbeat while a child CLI is working; a model call may remain quiet until it returns or times out. JSON results and blocked/manual-gate details remain on stdout. Only manual mode prompts for approval.

Failures add a `diagnostic` object containing a stable `code`, a failure `stage`, and a fixed description. Classified model-call evidence also records its call sequence and duration; graph failure state preserves the diagnostic in SQLite. Examples:

| Code | Meaning |
| --- | --- |
| `STORY_PATH_INVALID` | An absolute story path was rejected; supply a path relative to `--workspace`. |
| `STORY_READ_FAILED` | The story file could not be read. |
| `GEMINI_ENVELOPE_JSON_INVALID` / `GEMINI_ENVELOPE_INVALID` | The CLI envelope was malformed. |
| `GEMINI_RESPONSE_JSON_INVALID` | The model's requested JSON response could not be parsed. |
| `GEMINI_TOOL_ENVELOPE_INVALID` / `GEMINI_TOOL_CALL_INVALID` | A tool response violated the required structure or call identity rules. |
| `GEMINI_TOOL_NAME_UNOFFERED` / `GEMINI_TOOL_ARGUMENTS_INVALID` | The model requested an unoffered tool or supplied arguments that violate its object/parameter contract. |
| `GEMINI_SCHEMA_INVALID` | Structured plan output failed strict schema validation. |
| `CODEX_JSON_INVALID` / `CODEX_EVENT_INVALID` | Native JSONL or an event contract was rejected. |
| `CODEX_TURN_FAILED` / `CODEX_TURN_INCOMPLETE` | The native turn failed, was denied, or did not complete. |
| `CLI_TIMEOUT` / `CLI_START_FAILED` / `CLI_OUTPUT_LIMIT` | A bounded native process failed at the transport boundary. |
| `CLI_AUTH_REQUIRED` / `CLI_QUOTA_EXCEEDED` / `CLI_MODEL_UNSUPPORTED` | Native error text matched a fixed local category; this is classification, not independent provider verification. |
| `INTERNAL_ERROR` | No safe, specific classification is available. |

The finite catalog lives in `diagnostics.py`. Nonzero native CLI exits record a `cli_attempt_failed` event and bounded `cli_process` facts: provider, exit code, stdout/stderr byte counts, a stderr SHA-256 fingerprint, and recognized failure signals. Failed attempts remain visible even when a retry succeeds. Gemini generation retries one generic CLI execution failure after one second. The read-only Codex reviewer has its separate one-retry graph policy; Codex coding calls do not automatically repeat after an uncertain exit. Raw stderr, unknown exception bodies, provider output, stack traces, prompts, and source contents are never copied into diagnostic records. This does not remove existing task input from the private execution checkpoint or existing review evidence from the result.

Private event files live under the selected engine memory root in `diagnostics/<run-id>.jsonl`, normally `$env:USERPROFILE\.council\memory\engine\diagnostics`. The final CLI result provides `diagnostics_file` relative to that root and `diagnostics_status` (`available`, `capped`, or `unavailable`). Each file is capped at 1 MiB, and at most 200 eligible run files are created. Retention removes the oldest completed, unlocked timelines only; unrelated files and incomplete timelines are preserved. Capacity exhaustion, contention, unsafe links, and write failures disable persistence with a fixed `DIAGNOSTICS_UNAVAILABLE` warning, without changing the task outcome. Per-run process locks prevent duplicate writers; a short directory lock serializes retention and new-file creation. Locks are nonblocking. Reparse-point paths are rejected. These checks do not replace OS permissions or protect against a hostile same-user process replacing paths between filesystem operations.

Since 0.2.12, rejected Codex streams include a validated `native_event` object in failure results, model-call evidence and lifecycle JSONL. Its `reason` is a fixed local rejection code, `event_index` is the one-based JSONL line (zero before decoding or for empty output; EOF uses the next position), and `event_type`/`item_type` are allowlisted categories. Unrecognized category text becomes `unknown`; malformed categories become `invalid`. Raw messages, event IDs, paths, commands and unknown category strings are excluded. For example: `{"reason":"UNSUPPORTED_ITEM","event_index":27,"event_type":"item.completed","item_type":"unknown"}`. `CONTRACT_INVALID` is a fallback for an unexpected parser shape/type failure. Top-level codes and parser acceptance rules remain unchanged. These facts identify a rejected contract, not whether a partial implementation is correct; worker edits may already exist before rejection.

`run_finished` means this CLI segment ended, including a pause or failure; consult the result's `status` for the task outcome. Old checkpoints load with no diagnostic field and retain their historical generic errors. Updating diagnostics cannot reconstruct details discarded by an earlier failed run. The offline doctor creates no diagnostic timeline and makes no model request.

Python runs LangGraph and executes the workspace tools. By default, Python starts Gemini CLI for planning and failure diagnosis using its existing Google browser login. After plan approval, Python starts Codex CLI to implement the approved task using its existing ChatGPT login. Inference runs on each provider's hosted service; Python runs the graph, declared validation commands, and approval gates. The installed `council.ps1` wrapper is optional and invokes this same Python entry point.

Install Gemini CLI and Codex CLI separately, and keep them updated through their normal installers. Sign in to Gemini with your Google account and to Codex with ChatGPT (`codex login`). Normal new runs require neither `OPENAI_API_KEY` nor `GEMINI_API_KEY`. The offline doctor checks graph construction, SQLite, CLI identity and presence, Gemini OAuth-cache presence, and Codex native login status without extracting token values or calling a model. It records observed CLI versions but does not require an exact release. `transport_readiness` reports these local checks; `live_provider_access: unverified` remains accurate until an actual request succeeds. Missing or expired login must be repaired through the affected CLI's normal interactive login.

| Role | Model setting | Provider setting | Default |
|---|---|---|---|
| Orchestrator | `COUNCIL_ORCHESTRATOR_MODEL` | `COUNCIL_ORCHESTRATOR_PROVIDER` | `codex-cli` / `gpt-6.1-sol` |
| Investigator | `COUNCIL_INVESTIGATOR_MODEL` | `COUNCIL_INVESTIGATOR_PROVIDER` | `codex-cli` / `gpt-6.1-sol` |
| Coder | `COUNCIL_CODER_MODEL` | `COUNCIL_CODER_PROVIDER` | `codex-cli` / `gpt-6.1-sol` |
| Reviewer (autonomous runs) | `COUNCIL_REVIEWER_MODEL` | `COUNCIL_REVIEWER_PROVIDER` | `codex-cli` / `gpt-6.1-sol` |

The standard provider is `codex-cli` for every role. Reasoning roles receive a text-only adapter; coder and reviewer retain their existing role-specific worker/review interfaces. Set `COUNCIL_CODEX_CLI_PATH` to the absolute Codex executable if it is outside the normal Windows desktop-app location. The engine records executable paths, models, CLI versions, and timeouts in each new checkpoint. Explicit legacy provider overrides and saved settings remain readable; they are not required for the standard run. `CODEX_HOME`, when configured, retains Codex's normal login location. No adapter extracts or copies OAuth tokens. Legacy Gemini settings apply only to an explicitly selected historical/mixed configuration.

For reasoning roles and legacy saved runs, the explicit optional API providers remain `gpt` and `gemini`, requiring `OPENAI_API_KEY` and `GEMINI_API_KEY` respectively. Selecting either provider explicitly uses its provider-specific default model unless you also supply a model. A `gemini*` model without an explicit provider selects CLI. Credentials for optional APIs remain local environment values. The Python engine does not automatically read `.env` files.

The optional API backends pin the standard OpenAI and Gemini Developer API endpoints; custom gateways and Vertex are not configured. OpenAI uses Responses API without temperature. The CLI child deliberately selects cached Google OAuth and does not inherit API-key/Vertex authentication switches. Model/provider/settings are saved in v4 configuration for autonomous runs (four roles) or v3 for new manual/bypass runs (three roles). Existing v1 API and v2 two-role runs retain their original model settings and coding route when resumed. Existing API runs retain their key requirements. Legacy checkpoints without model configuration remain preserved but cannot resume.

The Gemini CLI transport starts in a private temporary working directory and passes the conversation over stdin as JSON. It validates the actual merged native settings before each call, disables native file/command tools, hooks, skills, project directory discovery, and agents, and adds a deny-all tool policy. Extensions are disabled and MCP servers are excluded through a sentinel allowlist. Existing managed settings, corporate restrictions, folder trust, and user profile files are preserved; incompatible enforced settings cause a failure rather than a bypass. The CLI's global `GEMINI.md` guidance and normal private session/cache behavior may still apply. Gemini model-response tools are described as JSON data and executed by LangGraph. Planning receives only read-only graph tools.

Some Gemini CLI builds emit an invalid empty tool declaration when all native tools are disabled. The transport uses a per-child compatibility shim only when it recognizes the required internal shape, and verifies effective text-only isolation before the model call. It does not edit the installed CLI, enable tools, change login, or relax policy. If an updated CLI changes that shape, the request fails with a compatibility diagnostic instead of proceeding with unverified tools. Codex output must still satisfy the bounded native event contract. Requests and combined process output are each bounded to 4 MiB, each model response to 16 graph tool calls, and Gemini CLI invocation deadlines to 180 seconds for inspection/plain calls and 600 for structured calls under new policy 2 (legacy snapshots retain 180). CLI process failures expose static categories rather than raw stderr.

The Codex worker launches `codex exec --json --approve-for-me --ephemeral` in the approved task working directory, with task/guidance over stdin and forced saved ChatGPT authentication. The review flag itself selects workspace-write; the CLI rejects combining it with an explicit `--sandbox` flag. Native rules, managed settings, hook trust, and existing user configuration remain in force; no dangerous bypass or ignore-rule flags are used. Each task rechecks the pinned version and login. A completed native turn and final response are required. Nonfatal diagnostic items and completed failed commands/patches during native repair are recorded as counts without their raw messages; fatal, denied, unknown and incomplete events fail the graph. LangGraph independently verifies the resulting work. Input and combined output are bounded to 4 MiB and each task to 600 seconds. Normal timeouts kill the child process tree. Background descendants whose parent has already exited are not guaranteed to be reaped; pipe hangs fail after bounded waits. This worker is not an additional OS sandbox.

Codex performs native coding after plan acceptance; LangGraph independently runs the plan's declared verification commands afterward. Failures go to Gemini for diagnosis, then back to Codex for bounded repairs. Successful verification and workspace audit complete autonomous runs; manual mode retains Gate 2. Accepted target-file lists describe task scope; they are not a filesystem allowlist. Codex retains the native sandbox's permissions, including any existing writable roots and managed restrictions. Declared targets and safe source files under the task working directory are SHA256-hashed before/after native coding, including failed turns. Source snapshots use existing private/generated/link exclusions, the 20,000-entry discovery bound and a 64 MiB byte budget. An incomplete inventory fails explicitly, before dispatch when baseline collection fails. Extra native file-change events outside the snapshot retain unknown before hashes. Excluded/generated files, links and effects outside that directory remain unobserved unless declared or reported; this is not a shell sandbox or exclusive attribution against concurrent writers.

Each call records role, transport/provider, requested model, effective settings, timestamp, outcome, and available usage. CLI version, Codex native thread IDs, and Gemini CLI-reported model aggregates are labeled explicitly; they are not presented as independently confirmed provider response identities. Missing provider request IDs remain unknown. No prompts, response content, authorization headers, or raw error bodies are copied into model-call evidence. The checkpoint still contains task input, approved plans, and execution state, while Gemini CLI may maintain its own native private session cache.

Planning has bounded read-only file listing, text search, and file reads before producing the approval plan. Shared Council guidance, the selected profile, specialist instructions, and applicable project instructions are assembled explicitly. Private onboarding history is not automatically sent to providers. Guidance is limited to 64 KiB per file and 192 KiB total; workspace tool reads are limited to 256 KiB per file.

Native approval pauses use the same run ID when resumed. Nodes may run again after a crash; external commands should be safe to repeat. Avoid running two installers or two processes for the same run concurrently. Close engine processes before updating the runtime. Installation needs package-index access; regular reuse and `-ValidateOnly` make no package downloads.

The orchestrator and investigator remain separate. Plans declare task working directories and test commands. Manual final approval includes the plan, declared command results, engine-tool file hashes, model-call evidence, and workspace validator outcome. Autonomous final results include review counters, accepted-plan digest, command results, file-change evidence, and workspace audit outcome. File-change inventory covers engine file tools, declared native targets, bounded task-directory source snapshots, and observed native file-change events; other subprocess side effects are not completely inventoried. Review phases not performed by the engine are explicitly marked unverified. A zero-exit verification command is evidence about that command, not proof that all required tests ran. Review the corporate pre-submit SOP and repository diff before merging.

Private engine state belongs beneath the canonical Council's `memory/`. Shared skill definitions remain in its `skills/` directory. The historical engine under `legacy/` is an inactive archive.

## Native turn accounting (0.2.19)

The pinned Codex command status `declined` is recognized only for completed command items with null or nonzero signed 32-bit exit codes. Evidence retains `cli_declined_command_count`, never the denied command/output. A final response and completed turn are still required; actual turn failures, malformed events and review-only tools remain terminal. Denied commands are not reissued, permissions are unchanged, and independent declared verification decides success. Unknown statuses produce finite `INVALID_ITEM_STATUS` feedback rather than being mislabeled as failed turns. Source snapshot failures use `NATIVE_INVENTORY_LIMIT` or `NATIVE_INVENTORY_FAILED`; a failed inventory never certifies a clean working tree.

Generated `.artifacts` directories are excluded from bounded discovery and native source inventories, alongside existing build, coverage and test-result directories. Their evidence files are preserved on disk; ordinary source and reference assets still participate in the unchanged byte and traversal limits. Generated evidence must not be declared as implementation source targets.

## Planning source failures (0.2.20)

An exact built-in missing-file exception from a planning read, list or search returns fixed `SOURCE_MISSING` unavailable-evidence feedback. It does not retry the request or extend the 12-round inspection budget. A missing listing/search root is unavailable rather than an observed empty directory. Missing files during coding, derived exceptions, permission errors and other I/O failures remain terminal. Existing boundary exclusions and link checks are unchanged.

Invoked tool failures emit `tool_failed` with finite `tool_failure` facts: an allowlisted tool name, its 1-based position within that model response (1–16), and a fixed reason (`SOURCE_MISSING`, `PERMISSION_DENIED`, `NOT_A_DIRECTORY`, `IS_A_DIRECTORY`, `INVALID_PATH`, `IO_ERROR` or `TOOL_ERROR`). Terminal diagnostics and durable tool history retain these facts. Failure receipts omit request arguments, paths, file contents and exception text. The failed tool's cause remains chained internally. Success receipts retain their existing bounded observations. These diagnostics do not recover the failed request from historical runs whose error details were discarded.

## Evidence-informed revision (0.2.21)

New autonomous runs persist revision_evidence_policy_version=2. Before structured revision, unresolved technical findings may receive one read-only inspection response, with at most 16 tool requests. It consumes remaining rounds from the SAME persisted 12-round planning inspection budget. Initial inspection still has its original limit; revision and feedback recovery never reset it. With no remaining rounds or no summary, revision uses existing evidence and explicitly retains the limitation. A malformed Gemini response receives one formatting retry within the same round. Only the existing architect read/list/search tools are offered; missing/excluded sources return unavailable feedback while actual permission/I/O failures remain terminal.

New inspection calls are labeled plan_revision_inspection, use the saved plain-call deadline, and retain bounded private receipts. Structured revision retains its original deadline. The revision prompt requires concrete finding-to-task/interface/verification corrections; the independent reviewer still controls finding closure and acceptance. Review/revision ceilings, no-progress rules, accepted-plan digests, permission boundaries and test-repair budgets are unchanged. This improves access to evidence; it does not guarantee a model will resolve a finding or that a live application story will pass.

Missing policy fields load as version 1. Existing runs retain the original revision call order and do not silently gain new dispatches. Start a NEW autonomous run to use policy 2; installing this version does not migrate or replay a blocked checkpoint. Manual/bypass runs also retain policy 1. As before, crashes may replay an in-flight node and external request; this is not exactly-once model execution.

## Graph readiness (0.2.22)

New autonomous runs record `readiness_policy_version: 2`. Planning and review examine prerequisites across the entire graph, including late integration/build/browser work: tools, dependency versions and lifecycle policy, runtime permissions, production module loading, services, and authentication/authorization. Readiness is an initial prefix of ordinary tasks with `kind: readiness`, green verification and `readiness_for` listing later implementation task IDs. Together they cover every implementation task. The reviewer checks that probes demonstrate the actual required capability; a printed message or helper test cannot establish browser/component readiness, and mocked component authentication cannot establish a live writer session.

For phase orchestration (0.2.31), readiness coverage is local to the current phase task plan. A prerequisite-only phase may contain only readiness tasks, each with empty `readiness_for`; it does not need fake implementation work or references to future phase IDs. Mixed phase plans still require an initial readiness prefix covering all current-plan implementation tasks. Planner, reviewer, revision/reset, preflight and worker guards use the same rule. Every readiness task still needs executable green verification, and a phase must be reviewed, accepted and successfully verified before the next phase is planned. Monolithic plans retain the existing implementation/coverage requirement. Task/roadmap values and accepted digests have no new fields or migrations.

Readiness tasks resolve scoped setup problems and run exact reviewed commands before feature work. They use the existing worker/prover/investigator flow and initial attempt plus at most two repairs. Successful command receipts and completed readiness tasks are required before later dispatch. Exhausted setup verification reports `READINESS_FAILED`; implementation is not dispatched. No extra model loop, budget increase, permission injection, automatic browser login, or test-command rewriting is added. Accepted command corrections require a reviewed new plan. Crash replay still requires repeat-safe setup and commands.

Every candidate must cover newly added tasks and keep all proposed tasks pending. As an exception to the older terminal-initial-planning rule above, an initial readiness-contract rejection enters the existing bounded revision path with finite correction feedback. Other initial failures retain their previous handling. Revised candidates use the same checks and limits. CLI final and planning-blocked output includes a `readiness` summary with policy, pending/ready/blocked state and one-based readiness/covered task positions; no probe output or session material is added to diagnostics.

For example, a readiness task can cover the later component integration and browser acceptance tasks by installing a compatible pinned browser, proving production bundling/mount/event handling under the intended Deno permissions, and independently verifying the live test browser's authenticated writer access. Inspect the repository's installation and lifecycle-script policy before selecting versions. If required user interaction is unavailable, report that prerequisite as blocked rather than substituting a mock. Version or reachability checks alone do not prove the complete path.

Missing policy fields load as version 1, including historical blocked/failed checkpoints. Manual/bypass new runs also retain version 1. Default task fields (`kind: implementation`, empty `readiness_for`) do not alter historical accepted-plan digests. Start a new autonomous run for readiness; installation does not replay partial work. Readiness is a point-in-time prerequisite check, not a guarantee against every future failure. Application tests remain necessary. Unplanned dependencies introduced during native coding are not automatically discovered by this task contract, and declared edit targets remain scope descriptions rather than a filesystem sandbox.

## Bounded arbiter recovery (source implementation)

New autonomous source runs enable recovery policy 1. `--recovery disabled` selects the original terminal behavior for a new run. Checkpoints without a recovery policy remain disabled, keep their historical identity digests, and are never silently upgraded. Manual/bypass runs retain their existing gates and do not enable recovery. Resume preserves the recorded policy; policy selection applies only at run creation.

The arbiter owns a single recovery path: capture an incident, propose a finite action, admit it deterministically, dispatch existing graph nodes, and observe their actual result. Known cases need no additional model call. Ambiguous eligible incidents use the configured orchestrator role with strict structured output. An arbiter failure terminates rather than recursively recovering itself. No model/provider fallback, arbitrary resume node, native permission bypass, engine self-edit or runtime replacement is added.

Supported decisions include verifying observed partial native-worker output after timeout; correcting investigator-identified command/prerequisite problems through normal plan preflight and independent review; and refreshing affected stale proofs through the normal prover. Concrete feature defects keep the existing investigator/worker/prover repair loop. A cosmetic replan that retains a known-invalid command fails with `RECOVERY_NO_PROGRESS`; changing task names or descriptive wording does not replenish the incident lineage budget.

Policy 1 admits at most two strategies per incident lineage and 32 per run, also bounded by the original graph-step limit. Existing task repair and safe transport retries do not gain another allowance. A recovery plan gets initial synthesis, at most two independent reviews and one correction after synthesis. Original revision/review counts and finding ledgers remain cumulative. The already-existing strategy-reset runs before technical exhaustion where applicable; recovery does not reset it or create a second strategy-reset mechanism.

Partial-work verification requires recorded source observations bound to the failed call, accepted task, plan, phase and current sources. Revalidation happens across admission/dispatch and before verification. Proof refresh uses only previously successful commands with unchanged accepted bindings, reruns affected tasks, preserves still-valid proof and the scheduling cursor, and appends actual new records. A real failure during refresh can be repaired before continuing its durable queue. Recovery never rewrites old failures or declares success from file existence.

Incident/history records retain category, finite reason/action, original evidence references, budget snapshots, actual execution IDs, elapsed recovery time and separate proposed/admitted/dispatched/outcome stages. Diagnostics expose finite progress messages with these bindings. Raw tool output, credentials and model prose are not added. Exact pending recovery stages can resume from SQLite with `--resume`; terminal historical failures are not automatically replayed. A process crash with unrecorded side effects can still require reconciliation by an operator. This is in-process recovery, not an automatic process supervisor or an exactly-once external execution guarantee.

Timeout cleanup reuses the existing owned-process termination code and records whether the direct child exit was confirmed. That fact does not prove detached containers, networks, background descendants, or temporary directories were cleaned. Detached resources remain explicitly unobserved unless a trusted harness supplies finite cleanup evidence. Known unresolved cleanup stops recovery. The arbiter has no destructive discovery-based cleanup action: RATE-style orphan Compose stacks still require ownership-qualified harness cleanup or operator intervention. Native parser/input/inventory defects, credentials/permission failures, invalid identity, rejected approval, and exhausted hard budgets likewise remain explicit operator boundaries.

This source feature must be packaged and installed before an existing installed runtime gains it. Source verification does not attest a live provider, production SSO, fresh-client hook trust, or an unattended application repeat.

### Persisted node narration (asynchronous observer)

Node narration is an optional observer alongside execution, enabled by default for CLI graph runs. Set `COUNCIL_NARRATION_ENABLED=0` to disable it. CLI callbacks (`narration_hooks.py`) capture bounded task/phase context and structured node outcomes without inserting nodes or changing routes. Existing diagnostic facts remain authoritative; raw state/checkpoint payloads, provider transcripts and command stdout are not narration inputs or persisted narration content.

`narration.py` adds version-one `node_narration_jobs` and append-only `node_narrations` tables (with finite failure reasons in `node_narration_failures`) beside the existing observations in `observability.sqlite`. Jobs reference the original event, session and node visit. Atomic SQLite claims use a 90-second lease, owner-fenced publication and at most two claim attempts. Pending progress for the same visit is coalesced; completed narration retains source order independently of completion order. Limits are 64 outstanding jobs and 512 retained jobs per run, with at most 128 model attempts per run. A crashed worker's final expired lease becomes a stored fallback. SQLite/model/observer failure cannot approve, retry, repair or fail application work.

`narration_worker.py` runs as a hidden, isolated Python child. It uses the configured orchestrator provider/model through the existing tool-free structured adapter, with a separately enforced 60-second generation deadline. Narrator calls are attributed as `node_narration` in their own result accounting and do not increment graph model-call counts. The parent never waits for generation. Parent EOF requests bounded draining; a later node can restart a dead observer at most three times per process. Generated text references its source event and is checked for bounded length, private-content patterns, and unsupported readiness/verification/completion claims. These checks supplement grounding; generated prose is explanatory, never execution evidence.

The viewer reads the separate narration stream through a read-only endpoint. Delayed generations remain attached to their originating visit. A node's four-line ticker refreshes downward once per new blurb, with immediate replacement for reduced motion. Full text remains available in the inspector/title; event-derived fallbacks are labelled. Previously recorded runs remain event-derived unless actual narration was recorded; no historical model backfill is implied. Engine installation and viewer-server restart are required to activate the new writer and endpoint. A browser refresh alone updates static UI assets but cannot add a route to an already-running server.
