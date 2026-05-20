---
name: temporal-versioning
description: Use when modifying Temporal .NET workflow definitions that have running executions - detects breaking changes (reordering Activities/Timers, changing Activity types, adding/removing Commands), non-determinism errors during replay, or before deploying workflow code changes
---

# Temporal Workflow Versioning

Enforce workflow versioning when making breaking changes to Temporal workflow definitions to prevent non-deterministic errors in running workflows.

**Related skill**: `temporal-dotnet` covers Temporal .NET development fundamentals. This skill focuses specifically on **safe deployment of workflow changes**.

## Core Principle

**Temporal workflows must be deterministic** — every execution must produce the same Commands in the same sequence given the same input. Changing workflow code while workflows are running can break determinism and cause failures.

**The Iron Law: ALL breaking changes REQUIRE versioning. No exceptions.**

## Contents

- [Two Versioning Approaches](#two-versioning-approaches)
- [When to Use](#when-to-use) | [Breaking Changes Checklist](#breaking-changes-checklist)
- [.NET SDK Patching Process](#net-sdk-patching-process) — 3-step lifecycle
- [Common Non-Determinism Errors](#common-non-determinism-errors)
- [Code Review Questions](#code-review-questions)
- [Workflow Cutovers](#workflow-cutovers-for-major-rewrites) → [workflow-cutover-guide.md](workflow-cutover-guide.md)
- [Emergency: Non-Determinism in Production](#emergency-non-determinism-in-production)
- [Choosing Your Strategy](#choosing-your-strategy)
- [Verification Checklist](#verification-checklist) | [Common Rationalizations](#common-rationalizations)

---

## Two Versioning Approaches

### 1. Patching (For Isolated Changes)

Branch code within workflow using `Workflow.Patched()` / `Workflow.DeprecatePatch()`. Both old and new code paths coexist.

**When**: Small-to-medium changes (< 10 breaking changes), isolated modifications, in-flight workflows that must adapt mid-execution.

**Process**: 3-step cycle → [.NET SDK Patching Process](#net-sdk-patching-process)

### 2. Workflow Cutovers (For Major Rewrites)

Copy existing workflow to frozen V1 file, rewrite original with new logic. Both versions coexist until V1 executions complete.

**When**: Major redesigns (> 10 breaking changes), complete workflow restructures, can coordinate updates across all calling services.

**Process**: Copy → Freeze V1 → Modify V2 → Deploy Both → Monitor → Cleanup → [workflow-cutover-guide.md](workflow-cutover-guide.md)

### Worker Versioning (When Unavailable in Your Environment)

If Temporal's Worker Versioning feature (Build IDs, versioned worker pools) is unavailable in your environment, or all workers upgrade simultaneously through a single deployment pipeline, use Patching or Cutovers instead.

---

## When to Use

Use this skill when:
- Adding, removing, or reordering any command-producing API calls
- Modifying workflow logic that affects execution order
- Seeing non-determinism errors in workflow executions
- Code review detects workflow changes without versioning

Use **BEFORE** making any of these changes to workflow code.

### When NOT to Use

You don't need versioning for:
- Changes to Activity/Child Workflow **parameters, return values, or timeouts** (NOT types/IDs)
- Changes to Signal **parameters**
- Timer **duration** changes (except changing to 0)
- Adding/removing non-command-producing API calls (like `Workflow.Info`)
- Brand new workflows (no running executions exist)

---

## Breaking Changes Checklist

### REQUIRES Versioning (Command-Producing)

These API calls produce Commands and MUST be versioned if added/removed/reordered:

- [ ] **Activities** — `ExecuteActivityAsync`, `ScheduleLocalActivityAsync`
- [ ] **Child Workflows** — `ExecuteChildWorkflowAsync`
- [ ] **Timers** — `DelayAsync`, `WaitConditionAsync`
- [ ] **Signals** — `SignalExternalWorkflowAsync`
- [ ] **Nexus Operations** — `ExecuteNexusOperationAsync`
- [ ] **Workflow Termination** — `CompleteAsync`, fail, cancel, continue-as-new
- [ ] **Patched/DeprecatePatch** — Versioning calls themselves
- [ ] **Search Attributes** — `UpsertSearchAttributes`
- [ ] **Memos** — `UpsertMemo`
- [ ] **Side Effects** — `SideEffect`, `MutableSideEffect`

### Safe Changes (No Versioning Needed)

- Activity/Child Workflow: parameters, return types, execution timeouts
- Signal: input parameters
- Timer: duration changes (except to 0)
- Non-command APIs: `Workflow.Info`, `Workflow.UtcNow`, `Workflow.Random`
- Code refactoring that doesn't change command sequence

---

## .NET SDK Patching Process

Temporal .NET SDK uses three-step patching:

### Step 1: Add Patch (Deploy Changes Safely)

**When:** You need to change workflow logic while executions are running.

```csharp
[Workflow]
public class MyWorkflow
{
    [WorkflowRun]
    public async Task<string> RunAsync()
    {
        if (Workflow.Patched("my-change-id"))
        {
            // NEW CODE — runs for new executions
            result = await Workflow.ExecuteActivityAsync(
                (MyActivities a) => a.NewActivity(),
                new() { StartToCloseTimeout = TimeSpan.FromMinutes(5) });
        }
        else
        {
            // OLD CODE — runs for existing executions during replay
            result = await Workflow.ExecuteActivityAsync(
                (MyActivities a) => a.OldActivity(),
                new() { StartToCloseTimeout = TimeSpan.FromMinutes(5) });
        }

        return result;
    }
}
```

**Rules:**
- Use descriptive change ID (e.g., `"switch-to-payment-v2-api"`)
- Change ID must be unique within workflow
- Both code paths MUST be present
- `Patched()` returns `true` for new executions, `false` for replaying old ones

**Verify before deploy:**
```bash
dotnet test  # All tests including workflow replay tests
```

### Step 2: Deprecate Patch (Remove Old Code)

**When:** ALL workflows started before Step 1 have completed or passed the patch point.

**How to verify:** Check Temporal Web UI — search by `TemporalChangeVersion` metadata NOT containing your change ID. If none found, safe to proceed.

```csharp
[Workflow]
public class MyWorkflow
{
    [WorkflowRun]
    public async Task<string> RunAsync()
    {
        Workflow.DeprecatePatch("my-change-id");

        // ONLY NEW CODE — old code path removed
        result = await Workflow.ExecuteActivityAsync(
            (MyActivities a) => a.NewActivity(),
            new() { StartToCloseTimeout = TimeSpan.FromMinutes(5) });

        return result;
    }
}
```

**Critical Rules:**
- `DeprecatePatch` MUST be in **EXACT same location** as original `Patched` call
- Activity order before/after deprecation must match original
- Don't hoist `DeprecatePatch` to beginning of workflow
- Don't combine multiple deprecations in single deploy

**Common Error:**
```
Non-deprecated patch marker encountered for change my-change-id,
but there is no corresponding change command!
```
**Cause:** `DeprecatePatch` in wrong location or missing entirely.

### Step 3: Remove Deprecation (Clean Up)

**When:** ALL workflows with `DeprecatePatch` marker have completed or exceeded retention period (typically 30-90 days).

**How to verify:** Check Temporal Web UI — ensure NO running workflows have `TemporalChangeVersion = "my-change-id"`.

```csharp
[Workflow]
public class MyWorkflow
{
    [WorkflowRun]
    public async Task<string> RunAsync()
    {
        // Clean code — no versioning artifacts
        result = await Workflow.ExecuteActivityAsync(
            (MyActivities a) => a.NewActivity(),
            new() { StartToCloseTimeout = TimeSpan.FromMinutes(5) });

        return result;
    }
}
```

**If you need to change again:** Use NEW change ID (e.g., `"my-change-id-v2"`), start from Step 1.

---

## Common Non-Determinism Errors

| Error Message | Cause | Fix |
|---|---|---|
| `No command scheduled for event HistoryEvent(id: X, Some(MarkerRecorded))` | Removed `DeprecatePatch` before all workflows completed | Re-add `DeprecatePatch`, wait for retention |
| `Activity type of scheduled event 'OldActivity' does not match 'NewActivity'` | Changed activity without patching | Add `Patched()` with both code paths |
| `Non-deprecated patch marker encountered for change X` | `DeprecatePatch` missing or in wrong location | Add `DeprecatePatch` in exact location of original `Patched` |
| `Change id X does not match expected id Y` | Multiple patches, wrong order during replay | Ensure patches execute in same sequence |
| `Timer machine does not handle this event: MarkerRecorded` | Removed `DeprecatePatch` adjacent to another patch | Wait until adjacent patch also deprecated ([SDK bug](https://github.com/temporalio/sdk-core/issues/535)) |

---

## Code Review Questions

When reviewing workflow changes, ask:

1. **Does this PR modify a `[Workflow]` class?**
2. **Does it add/remove/reorder any command-producing calls?** (See checklist above)
3. **If yes, does it use `Workflow.Patched()` or new workflow type name?**
4. **Are BOTH code paths present if using `Patched()`?**
5. **If deprecating, have ALL old workflows completed?**
6. **Is `DeprecatePatch` in EXACT location of original `Patched` call?**

**Red Flags:**
- "Just a small change to the workflow"
- "No workflows are running" (without verification)
- Activity name change without patch
- Reordering activities without patch
- `DeprecatePatch` at beginning of workflow
- Multiple deprecations in one PR

---

## Workflow Cutovers (For Major Rewrites)

**When**: Breaking changes too extensive for patching (complete workflow restructure, 10+ changes).

**Core Pattern**: Copy existing workflow to frozen V1 file, modify original for new logic. Keeps original filename for new code — PR diffs show actual business changes.

| Factor | Cutover Better | Patching Better |
|---|---|---|
| Number of changes | > 10 | < 5 |
| Workflow structure | Major redesign | Isolated modifications |
| In-flight workflows | Don't need changes | Must adapt to changes |
| Coordination effort | Can coordinate callers | Many independent callers |

**Full implementation guide**: See [workflow-cutover-guide.md](workflow-cutover-guide.md) for complete 7-step process, model versioning, deployment coordination, gotchas, and timeline.

---

## Emergency: Non-Determinism in Production

**Symptoms:** Workflow tasks failing repeatedly, non-determinism errors in logs/UI, workflows stuck.

**Immediate Actions:**
1. **Don't panic** — data is NOT lost, workflows are paused
2. Identify the breaking change (check recent deploys)
3. **Option A — Rollback:** Deploy previous code version
4. **Option B — Fix Forward:** Add missing `Patched()` calls
5. Monitor Temporal Web UI for workflow recovery

**For Wedged Workflows:**
```bash
# Reset workflow to before problematic event
temporal workflow reset --workflow-id <ID> --event-id <ID before patch marker>
```

**Prevention:**
- Always test with workflow replay before deploying
- Use staging environment for workflow changes
- Review this skill's checklist in ALL workflow PRs

---

## Choosing Your Strategy

**Common Constraint:** Single deployment pipeline — all workers upgrade simultaneously.

| Scenario | Recommended Approach |
|---|---|
| Small workflow change (1-3 activities) | **Patching** (3-step process) |
| Medium workflow change (4-10 activities) | **Patching** (track multiple patch IDs) |
| Large workflow change (10+ activities) | **Workflow Cutover** (less error-prone than many patches) |
| Complete workflow rewrite | **Workflow Cutover** |
| Need to rollback quickly | **Patching** (deploy previous code) |
| Mid-execution changes required | **Patching** (only option) |

**Rule of Thumb:**
- < 3 code locations → Patching
- \> 10 code locations → Cutover
- Between → Judgment call based on complexity

---

## Verification Checklist

Before deploying workflow changes:

**Breaking Change Detection:**
- [ ] Reviewed all modifications to `[Workflow]` classes
- [ ] Identified all added/removed/reordered command-producing calls
- [ ] Confirmed change requires versioning (not in safe changes list)

**Step 1 — Adding Patch:**
- [ ] Used `Workflow.Patched("descriptive-change-id")`
- [ ] Both old and new code paths present
- [ ] Change ID is unique in this workflow
- [ ] All tests pass including replay tests
- [ ] Verified in staging environment

**Step 2 — Deprecating Patch:**
- [ ] Searched Temporal Web UI — zero workflows without change ID in metadata
- [ ] `DeprecatePatch` in EXACT location of original `Patched` call
- [ ] Only ONE deprecation per deploy
- [ ] No adjacent patches being deprecated simultaneously
- [ ] All tests pass

**Step 3 — Removing Deprecation:**
- [ ] Searched Temporal Web UI — zero workflows with change ID in metadata
- [ ] Retention period has passed since last execution with marker
- [ ] All tests pass
- [ ] Ready to use new change ID if future changes needed

---

## Common Rationalizations (STOP — Version It)

| Excuse | Reality |
|---|---|
| "It's just changing parameters" | If it changes command ORDER, version it |
| "No workflows are running" | Verify in Temporal Web UI first |
| "Tests pass" | Tests don't catch non-determinism on running workflows |
| "I'll patch it later if there's a problem" | Too late — workflows already failing |
| "The workflow is short-lived" | Even 5-minute workflows can be running during deploy |
| "This is the same activity, just renamed" | Activity type changes break determinism |
| "I'm only adding, not changing" | Adding commands mid-workflow breaks determinism |

**All of these mean: Use `Workflow.Patched()` or create new workflow version.**

---

## References

- [Temporal .NET Versioning Docs](https://docs.temporal.io/develop/dotnet/versioning)
- [Deterministic Constraints](https://docs.temporal.io/workflow-definition#deterministic-constraints) — also covered in `temporal-dotnet` skill's Golden Rules
- [Patching API Reference](https://dotnet.temporal.io/api/Temporalio.Workflows.Workflow.html)
- [Event History Walkthrough](https://docs.temporal.io/encyclopedia/event-history/event-history-dotnet)
- **Temporal Docs MCP**: Use `mcp_temporal-docs_search_temporal_knowledge_sources` tool (if available) for questions not answered here
