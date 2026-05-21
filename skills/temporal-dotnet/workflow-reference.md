# Workflow Reference — Temporal .NET

Detailed reference for advanced workflow APIs, activity options, timers, messaging, and versioning. Supplements the main SKILL.md.

> **Tip**: For workflow questions not covered here, use the `mcp_temporal-docs_search_temporal_knowledge_sources` tool (if available) to search official Temporal documentation.

---

## Contents

- [Advanced Workflow APIs](#advanced-workflow-apis)
- [Activity Options](#activity-options)
- [Timers & Delays](#timers--delays)
- [Messaging & Signals/Updates](#messaging--signalsupdates)
- [Versioning & Deployment](#versioning--deployment)

---

## Advanced Workflow APIs

### WaitConditionWithOptionsAsync

```csharp
// Advanced wait with timeout summary, condition check, and per-step cancellation
using var stepCts = CancellationTokenSource.CreateLinkedTokenSource(Workflow.CancellationToken);
await Workflow.WaitConditionWithOptionsAsync(new WaitConditionOptions
{
    TimeoutSummary = "Waiting for fulfillment update",
    ConditionCheck = () => _state.HasReceivedUpdate,
    CancellationToken = stepCts.Token,
    Timeout = TimeSpan.FromSeconds(_state.ExecutionOptions.CompletionTimeoutInSeconds),
});
```

### Custom Search Attributes

```csharp
// Define search attribute keys
private static readonly SearchAttributeKey<string> OrderIdKey =
    SearchAttributeKey.CreateKeyword("OrderId");

// Upsert in workflow (e.g., in update handler)
Workflow.UpsertTypedSearchAttributes(
    OrderIdKey.ValueSet(request.PlacedOrder.OrderId));
```

### Parallel Activity Execution

```csharp
// Run multiple activities in parallel
var (validateResult, pricingResult) = await Workflow.WhenAllAsync(
    Workflow.ExecuteActivityAsync<IValidateActivities, ValidateResponse>(
        a => a.ValidateAsync(input), activityOptions),
    Workflow.ExecuteActivityAsync<IPricingActivities, PriceResponse>(
        a => a.PriceAsync(input), activityOptions));
```

### Per-Step Cancellation

> **Important**: `CancelAsync()` does NOT work in Temporal workflows (async operations are non-deterministic). Always use synchronous `Cancel()` + `Dispose()`.

```csharp
// Method-scoped: using var for simple cases
using var stepCts = CancellationTokenSource.CreateLinkedTokenSource(Workflow.CancellationToken);
try
{
    await Workflow.ExecuteActivityAsync<IMyActivities, Result>(
        a => a.DoWork(input), options);
}
catch (Exception e) when (TemporalException.IsCanceledException(e))
{
    // Handle cancellation — reset state, log, etc.
    _state.Step = FulfillmentStep.Cancelled;
}
```

### Field-Level CancellationTokenSource (Cancel & Recreate)

When update handlers need to interrupt in-progress work and restart with new input, use a field-level CTS that is cancelled, disposed, and recreated. Workflow must implement `IDisposable` to clean up the field.

```csharp
[Workflow]
public class OrderWorkflow : IOrderWorkflow, IDisposable
{
    private CancellationTokenSource _processingCts;
    private bool _disposed;

    [WorkflowInit]
    public OrderWorkflow(OrderRequest request)
    {
        _processingCts = CancellationTokenSource.CreateLinkedTokenSource(
            Workflow.CancellationToken);
    }

    // Cancel current work and create fresh CTS for new work
    private void CancelAndRestart()
    {
        // Note: CancelAsync() won't work in Temporal workflows; use Cancel().
        try { _processingCts.Cancel(); } catch { /* may already be cancelled */ }
        try { _processingCts.Dispose(); } catch { /* defensive */ }
        _processingCts = CancellationTokenSource.CreateLinkedTokenSource(
            Workflow.CancellationToken);
    }

    public void Dispose()
    {
        Dispose(true);
        GC.SuppressFinalize(this);
    }

    protected virtual void Dispose(bool disposing)
    {
        if (!_disposed)
        {
            if (disposing) { _processingCts.Dispose(); }
            _disposed = true;
        }
    }
}
```

---

## Activity Options

```csharp
// From workflow — always use interface type:
var result = await Workflow.ExecuteActivityAsync<IMyActivities, MyResult>(
    a => a.DoWork(input),
    new ActivityOptions
    {
        StartToCloseTimeout = TimeSpan.FromSeconds(30),
        RetryPolicy = new RetryPolicy
        {
            InitialInterval = TimeSpan.FromSeconds(1),
            BackoffCoefficient = 2.0,
            MaximumInterval = TimeSpan.FromMinutes(1),
            MaximumAttempts = 5,
            NonRetryableErrorTypes = new[] { nameof(Errors.InvalidArguments) }
        }
    });
```

---

## Timers & Delays

### Timer Code Example

```csharp
// Configurable durations via input ExecutionOptions
await Workflow.DelayAsync(TimeSpan.FromSeconds(
    _state.ExecutionOptions?.ApprovalTimeoutSeconds ?? 3600));
```

### Timer Rules

| Rule | Details |
|------|---------|
| **Deterministic time changes** | Changing a timer to/from `Infinite`/`InfiniteTimeSpan` from/to an actual value is **non-deterministic** and will cause NDE |
| **Zero delay = 1ms server timer** | In .NET, `DelayAsync(TimeSpan.Zero)` creates a 1ms server-side timer (unlike some SDKs that skip it). This means changing 0 to/from a real value is safe, but resolution may not be precise |
| **Guard dynamic durations** | Always validate/assert durations from Activities or unvalidated input before using in timers. Dynamic values can cause NDE or surprising results |
| **Worker availability** | If Workers aren't running when a Timer fires, the `TimerFired` task waits. Activities may execute "late" — guard time-sensitive operations |
| **Million Timers Issue** | Scheduling timers at a fixed time across many workflows overwhelms resources. Add **jitter** to delay durations to prevent bottlenecks |
| **Configurable for testing** | Accept timer durations as `ExecutionOptions` input — enables fast CI/CD tests without lengthy waits |

---

## Messaging & Signals/Updates

### Signal Considerations

| Concern | Details |
|---------|---------|
| **Throughput** | ~few/sec sustained per execution, peaks to 10-20/sec. Higher? Reconsider if business entities should be separate workflows |
| **Unknown Signals** | ALL signals contribute to event history, even unhandled ones. Avoid piping unfiltered webhooks/producers to a workflow |
| **Dropped Signals** | Temporal will NOT drop signals, even during Closing. Buffered signals replay before Close/ContinueAsNew |
| **History limits** | Signals are subject to [per-execution signal count limits](https://docs.temporal.io/cloud/limits#per-workflow-execution-signal-limit) |

### Update Considerations

- Validation phase (`[WorkflowUpdateValidator]`) can inspect current workflow state but MUST NOT make external calls (no Activities)
- An `Update` blocks a workflow slot while waiting for response — keep handler logic fast or use `WaitConditionAsync`

### Propose/Apply Pattern for Side Effects

When signal/update handlers need to cause side effects (e.g., trigger an Activity), split into two stages:

1. **Propose** (in handler): Set the received input onto shared workflow state
2. **Apply** (in workflow main method): React to the proposed state change and execute side effects

```csharp
// Signal handler — propose only
[WorkflowSignal]
public Task SubmitPayment(PaymentRequest request)
{
    _state.PendingPayment = request;  // Propose
    return Task.CompletedTask;
}

// In RunAsync — apply side effects
while (!_state.IsComplete)
{
    await Workflow.WaitConditionAsync(() => _state.PendingPayment != null);
    var result = await Workflow.ExecuteActivityAsync<IPaymentActivities, PaymentResult>(
        a => a.ProcessPayment(_state.PendingPayment!), options);
    _state.PaymentResult = result;
    _state.PendingPayment = null;
}
```

> This pattern avoids concurrency issues from blocking inside message handlers. See [Handling Messages](https://docs.temporal.io/encyclopedia/workflow-message-passing#handling-messages).

### Query & Search Attribute Considerations

| Facility | Use For | Gotchas |
|----------|---------|---------|
| **Query** | Consistent, computed state from current history | Requires Workers running; takes cache entries; subject to message broker latency; only works for Open or un-purged Closed workflows |
| **Search Attributes** | Cross-workflow search/filtering for operations | **Eventually consistent** — not suitable for customer-facing search experiences. Values are NOT passed through DataConverter (security implication) |

---

## Versioning & Deployment

> **For comprehensive versioning guidance** — breaking changes checklist, 3-step patching lifecycle, workflow cutovers, non-determinism error table, code review questions, and emergency procedures — see the `temporal-versioning` skill.

### Strategy Selection

| Strategy | Use When |
|----------|----------|
| **Patched** (`Workflow.Patched("patch-id")`) | Simple/few changes to workflow logic; callers don't need updating |
| **Routed** (TaskQueue or WorkflowType) | Complex changes; team controls both callers and workers |
| Worker Versioning | Task-queue-level version routing |
| Protobuf v2 directory | Breaking contract changes |
| Continue-As-New | Preventing unbounded event history for long-running workflows |

### Patched Strategy Guidance

```csharp
if (Workflow.Patched("add-validation-step"))
{
    // New code path for new + future executions
    await ValidateAsync(input);
}
// Old code path continues for replaying executions
```

| Rule | Details |
|------|---------|
| **`changeId` is immutable** | Never rename a `changeId` — causes NDE for replaying executions |
| **Name for feature block** | Use feature names (`"payment-authorization"`) or specific fixes (`"hotfix-JIRA-123"`) |
| **Loops require decisions** | Version the whole loop (same `changeId`) or per iteration (unique `changeId` per index). Many iterations → use ContinueAsNew to prevent history explosion |
| **Rolling deployment race** | New patched code writes Version marker → crashes → old Worker picks up → NDE. Mitigate by always versioning entire workflow definition before deployment |
| **Removing old versions** | Wait for Namespace retention period before removing old version code blocks. If a Query exposes version-dependent state, keep version blocks until retention expires |

### Routed Strategy (Alternative)

| Variant | Pros | Cons |
|---------|------|------|
| **WorkflowType** (`MyWorkflowV2`) | No Worker deployment changes; discrete per Type | Callers must update; harder Git diffs |
| **TaskQueue** (`PaymentsV2`) | Easy to decommission by observing Workers | Callers must update; exponential Worker count |

### ContinueAsNew

**Restrict Workflow Execution Lifetimes**: Frequently use ContinueAsNew for long-running workflows to prevent unbounded event history. Frequency driven by how often you ship — e.g., daily deploys → ContinueAsNew daily.

### Message/Schema Versioning

- **Prefer additive, evolutionary changes** — add new fields, keep old ones until safe to deprecate
- Activity inputs are NOT in history (safe to change); responses ARE (impact determinism)
- **Always use Replay tests** to verify schema compatibility with currently open executions
- See [Messaging foundation](https://github.com/temporalio/temporal-jumpstart/blob/main/docs/foundations/Messaging.md) for Protobuf compatibility rules
