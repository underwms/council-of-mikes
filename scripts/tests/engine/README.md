# Council engine test fixtures

These tests use scripted provider boundaries with real graph execution, verifier
subprocesses, temporary workspaces and SQLite checkpoints. No provider account
or feature run is required.

## Select a policy fixture explicitly

`graph_workspace` creates files and a plan without choosing a run policy. The
fixtures in `graph_fixtures.py` select policy values independently of production
model defaults:

| Fixture | Approval | Review | Revision evidence | Readiness | Orchestration | Graph integrity |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `current_autonomous_run` | autonomous | 2 | 2 | 2 | 2 | 2 |
| `legacy_lifecycle` | historical/manual | 1 | 1 | 1 | 1 | 1 |
| `legacy_monolithic_run` | autonomous compatibility | 2 | 1 | 1 | 1 | 2 |

`current_autonomous_run` includes an executable readiness prefix and one final
roadmap phase. `test_fixture_policies.py` captures state from actual fresh CLI
startup and compares it with this independently declared fixture contract. A
default-policy change must be reconciled deliberately; fixture values do not
silently follow `CouncilState` defaults.

Existing imports of `lifecycle` remain supported as a documented alias for
`legacy_lifecycle`. This preserves historical tests and supported manual-mode
behavior. New current-policy graph tests should use `current_autonomous_run`.
The older partial-policy revision helper is explicitly named
`legacy_monolithic_integrity_setup`; individual compatibility tests may still
enable a particular later policy to isolate its contract.

## Run policy scopes separately

From the Council root:

```powershell
runtime/Scripts/python.exe -I -m pytest -p no:cacheprovider scripts/tests/engine -m current_policy
runtime/Scripts/python.exe -I -m pytest -p no:cacheprovider scripts/tests/engine -m legacy_policy
runtime/Scripts/python.exe -I -m pytest -p no:cacheprovider scripts/tests/engine -m 'not current_policy and not legacy_policy'
```

Use a fresh `--basetemp` under `.council/work` for each run. The local Windows
environment may require the documented exclusion
`-k 'not test_specialist_instruction_symlink_cannot_escape_canonical_packages'`;
report that exclusion rather than treating the privilege-dependent fixture as
verified.

Collection marks tests using the current fixture as `current_policy` and tests
using a version-one/monolithic fixture as `legacy_policy`. Unmarked tests are
standalone unit/transport coverage, including isolated policy contracts; they
are not implicitly current-flow acceptance. These markers describe fixture
scope, not a claim of real feature completion.

## Completion-proof regression

`test_completion_evidence.py` lets task verification finish, pauses before
gatekeeper, changes either a declared deliverable or its verifier, then reopens
the SQLite-backed graph. Both policy modes must reject completion with
`GRAPH_EVIDENCE_INVALID`. Unchanged-source controls must still complete.

The tests are proven by disabling completion-proof enforcement only in a private
source copy: all four changed-source cases must fail, while both unchanged
controls pass. Never disable enforcement in the active engine to run this check.
