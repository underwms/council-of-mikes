---
name: temporal-dotnet
description: Use when developing Temporal workflows, activities, nexus services, workers, or clients in .NET, or when writing unit/integration tests for Temporal components, or when debugging Temporal SDK mocking issues with non-virtual methods
---

# Temporal .NET Development

Guide for building production-ready Temporal applications in .NET using the official Temporal SDK.

**Tech Stack**: .NET 10+, Temporalio SDK v1.10.0 (via official Temporalio NuGet), xUnit, Moq, Protocol Buffers

**Wrapper Libraries**: Use the official `Temporalio` NuGet package directly, or your organization's wrapper library if it standardizes client/worker registration, hierarchical config binding, payload converters, tracing interceptors, or testing utilities. If you use a wrapper library, verify which packages it brings transitively and add any missing packages such as `NexusRpc` explicitly when needed.

**References**:
- [Temporal .NET SDK](https://github.com/temporalio/sdk-dotnet) | [Temporal Jumpstart Foundations](https://github.com/temporalio/temporal-jumpstart/tree/main/docs/foundations)
- **Temporal Docs MCP**: Use `mcp_temporal-docs_search_temporal_knowledge_sources` tool (if available) for questions not answered here.

## Contents

- [Core Principles](#core-principles) | [When to Use](#when-to-use-temporal)
- [Workflow Development](#workflow-development) — Golden Rules, 6-step pattern, error handling
- [Activity Development](#activity-development) — Adapter pattern, types, best practices
- [Worker Configuration](#worker-configuration) — Setup, registration patterns
- [Client Usage](#client-usage) — Starting workflows, ID strategies
- [Nexus Services](#nexus-services) — Cross-namespace communication → [nexus-reference.md](nexus-reference.md)
- [Testing](#testing) — SDK mocking constraints → [testing-reference.md](testing-reference.md)
- [Protobuf](#protobuf-contracts) — Schema design → [protobuf-reference.md](protobuf-reference.md)
- [Timers](#timers--delays) | [Messaging](#messaging--signalsupdates) | [Versioning](#versioning--deployment)
- [Configuration](#configuration) — Settings, registration → [configuration-reference.md](configuration-reference.md)
- [Common Pitfalls](#common-pitfalls)

---

## Core Principles

1. **Workflows must be deterministic** — same inputs always produce same outputs
2. **Activities handle all side effects** — I/O, network calls, non-deterministic ops
3. **Workers are stateless** — all state lives in Temporal server
4. **Event sourcing drives execution** — workflows replay from event history
5. **Single message per operation** — one request object, one response object
6. **Protobuf for contracts** (recommended) — versioned, type-safe, auto-generated models

---

## When to Use Temporal

**Good fit**: Long-running processes, durable orchestration, retry/compensation logic, cross-service coordination, workflows waiting for external events.

**Not ideal**: Simple request/response APIs, high-frequency low-latency ops (>1000 ops/sec per workflow), pure data transformations without orchestration.

---

## Workflow Development

### Workflow Structure (6-Step Pattern)

```csharp
[Workflow]
public class OrderWorkflow
{
    private OrderState _state = new();  // 1. Initialize state

    [WorkflowInit]  // Optional: receive input in constructor
    public OrderWorkflow(OrderRequest request)
    {
        _state = new OrderState { OrderId = request.OrderId };
        // Workflow.CancellationToken is available here
    }

    [WorkflowQuery]                                      // 2. Read handlers
    public OrderState GetState() => _state;

    [WorkflowUpdate]                                     // 3. Write handlers
    public async Task<UpdateResponse> ProcessUpdate(UpdateRequest req) { /* ... */ }

    [WorkflowUpdateValidator(nameof(ProcessUpdate))]     // 3b. Validate before update
    public void ValidateProcessUpdate(UpdateRequest req)
    {
        if (req is null) throw new ApplicationFailureException("Request required",
            nameof(Errors.InvalidArguments), nonRetryable: true);
    }

    [WorkflowRun]
    public async Task<OrderResult> RunAsync(OrderRequest request)
    {
        // 4. Validate inputs
        if (string.IsNullOrEmpty(request.OrderId))
            throw new ApplicationFailureException("OrderId required",
                nameof(Errors.InvalidArguments), nonRetryable: true);

        // 5. Load context (via activity — note interface-based generic)
        var config = await Workflow.ExecuteActivityAsync<IConfigActivities, ConfigResult>(
            a => a.LoadConfig(), new() { StartToCloseTimeout = TimeSpan.FromSeconds(10) });

        // 6. Perform behavior (activities, timers, waits)
        var result = await Workflow.ExecuteActivityAsync<IOrderActivities, OrderResult>(
            a => a.ProcessOrder(request), new() { StartToCloseTimeout = TimeSpan.FromSeconds(30) });

        await Workflow.WaitConditionAsync(() => Workflow.AllHandlersFinished);
        _state.Status = "Completed";
        return result;
    }
}
```

### Workflow Golden Rules

| Rule | Details |
|------|---------|
| **Deterministic code only** | No `DateTime.Now`, `Guid.NewGuid()`, `Random`, `Thread.Sleep`, or I/O |
| **Use `Workflow.*` APIs** | `Workflow.UtcNow`, `Workflow.DelayAsync()`, `Workflow.NewGuid()` |
| **No logging in workflows** | Never call `Workflow.Logger`, `ILogger`, `LoggerMessage`, or any logging API in workflow code. .NET logging providers (Serilog, NLog, OpenTelemetry, console) use async I/O, background threads, or timers that cause non-determinism errors during replay. Capture diagnostic context in workflow state; log from activities only. See [sdk-dotnet#435](https://github.com/temporalio/sdk-dotnet/issues/435) |
| **Encapsulate state** | Single `_state` object; capture all inputs and activity responses; avoid boolean flags — prefer null checks; always expose via `[WorkflowQuery] GetState()` |
| **Business failures ≠ execution failures** | Capture business failures as state + search attributes, not exceptions. A workflow that did as instructed didn't "fail" |
| **Don't leak implementation details** | Handle Activity errors inside workflow; transform for callers. Don't expose raw Activity exceptions |
| **Workflows own their lifecycle** | Callers should NOT set timeouts. Use input `ExecutionOptions` and internal `WaitConditionAsync` for TTL |
| **Configurable durations** | Accept timeouts as input `ExecutionOptions` for testability across environments |
| **Pass timestamps as input** | Include `Timestamp` in input rather than using `Workflow.Info.StartTime` — avoids Worker unavailability skew |
| **Meaningful workflow IDs** | Business IDs like `order-{orderId}`, not random UUIDs. Pattern: `{entity-type}-{entity-id}` |
| **`.workflow.cs` suffix** | Enables `.editorconfig` rules for workflow files |
| **Implement `IDisposable`** | When workflow owns a `CancellationTokenSource` field, implement `IDisposable` to clean up. Use `Cancel()` + `Dispose()`, NOT `CancelAsync()` |

### Workflow Interface Pattern

```csharp
[Workflow]
public interface IOrderWorkflow
{
    [WorkflowRun]   Task<OrderResult> RunAsync(OrderRequest request);
    [WorkflowUpdate] Task<FulfillmentResponse> FulfillmentUpdate(FulfillmentRequest request);
    [WorkflowQuery] OrderState GetOrderState(GetOrderStateRequest? request);
    [WorkflowSignal] Task CancelOrder(CancelRequest request);
}
```

### Activity Execution via Interface

Always use **interface type**, not concrete class — enables DI-based activity registration.

```csharp
// ✅ Interface-based (matches DI registration)
var result = await Workflow.ExecuteActivityAsync<IValidateActivities, ValidateResponse>(
    act => act.ValidateProductsActivityAsync(request), activityOptions);

// ❌ Concrete class (won't resolve from DI)
var result = await Workflow.ExecuteActivityAsync(
    (ValidatedActivities a) => a.ValidateProductsActivityAsync(request), activityOptions);
```

### Lifecycle Management

- Enforce TTL in a background `WaitConditionAsync` — don't let callers control workflow lifetime
- Handle cancellations explicitly via `TemporalException.IsCanceledException(e)`
- **`CancelAsync()` forbidden** in workflows — use synchronous `Cancel()` + `Dispose()`. See [workflow-reference.md](workflow-reference.md) for field-level CTS pattern
- Use `Workflow.AllHandlersFinished` to wait for update handlers before exit
- Use `Workflow.WhenAllAsync()` for parallel activity execution
- **ContinueAsNew** for long-running workflows — frequency driven by deploy cadence

**Advanced APIs**: See [workflow-reference.md](workflow-reference.md) for `WaitConditionWithOptionsAsync`, custom search attributes, parallel execution, and per-step cancellation patterns.

### Error Handling Strategy

```
Business failures  → capture in state + search attributes (NOT thrown)
Execution failures → throw ApplicationFailureException
Validation errors  → throw ApplicationFailureException(msg, errorType, nonRetryable: true)
Activity errors    → catch and transform for callers (don't leak implementation details)
Cancellation       → detect via TemporalException.IsCanceledException(e)
Diagnostics        → capture context in workflow state; log from activities only (NEVER log in workflows)
```

> A Temporal Failure thrown for a business condition shows the Execution as "failed" and skews `workflow_failed` metrics. Use state + queries + search attributes for business outcomes instead.

---

## Activity Development

Activities implement the **Adapter pattern** — bridging Temporal orchestration with existing API clients, DB connections, and business logic. Non-deterministic code is expected.

### Activity Types

| Local Activity | Regular Activity |
|----------------|------------------|
| Fast (< 60s), virtually guaranteed to succeed | May take > 60s, may fail |
| No I/O, no heartbeat | I/O, heartbeat if > 2 min |
| Config lookups, validations, calculations | API calls, DB ops, file ops |

**Local Activity Gotchas**: Can slow workflows (failures cause entire Workflow Task to fail); may be retried even when they didn't fail.

> **⚠️ CRITICAL: Local Activities Retry Forever by Default**
>
> Local activities use the **same default retry policy** as regular activities: `MaximumAttempts = 0` (unlimited), exponential backoff starting at 1s, capped at 100s. Unlike regular activities where you typically set explicit retry policies, local activities are often configured with only `StartToCloseTimeout` — which does NOT bound retries.
>
> **What happens when a local activity throws:**
> 1. The exception causes the **entire Workflow Task to fail** (not just the activity)
> 2. No activity result is recorded in history
> 3. The Workflow Task is retried → the local activity re-executes
> 4. With unlimited retries and exponential backoff, this continues **indefinitely**
> 5. The workflow stays in "Running" state — the exception is **never surfaced** to the caller
>
> This is especially dangerous for deterministic operations (AutoMapper mappings, tender type conversions, enum switches) that will **always** throw the same exception. The retry loop provides zero recovery value.
>
> **Fix:** Always set `RetryPolicy = new RetryPolicy { MaximumAttempts = 1 }` on `LocalActivityOptions` for deterministic local activities. Centralize via a helper method:
>
> ```csharp
> private LocalActivityOptions GetLocalActivityOptions(
>     TimeSpan startToCloseTimeout, CancellationToken? cancellationToken = null)
> {
>     return new LocalActivityOptions
>     {
>         StartToCloseTimeout = startToCloseTimeout,
>         RetryPolicy = new RetryPolicy { MaximumAttempts = 1 },
>         CancellationToken = cancellationToken ?? _cancellationToken
>     };
> }
> ```
>
> A shared helper like `GetLocalActivityOptions()` is the recommended production pattern.
> See [testing-reference.md § Local Activity Retry Behavior Tests](testing-reference.md#local-activity-retry-behavior-tests) for proof-of-concept tests.

### Activity Best Practices

```csharp
public class OrderActivities : IOrderActivities
{
    private readonly IOrderService _orderService;
    public OrderActivities(IOrderService orderService) => _orderService = orderService;

    [Activity]
    public async Task<OrderResult> ProcessOrder(OrderRequest request)
    {
        using var cts = CancellationTokenSource.CreateLinkedTokenSource(
            ActivityExecutionContext.Current.CancellationToken,
            ActivityExecutionContext.Current.WorkerShutdownToken);
        return await _orderService.ProcessAsync(request, cts.Token);
    }
}
```

| Rule | Details |
|------|---------|
| **Inject dependencies at startup** | Don't create expensive clients per call |
| **All logging happens here** | Activities are the ONLY place to use `ILogger`/`LoggerMessage`. Workflows must never log — capture diagnostic context in state, pass to activities for logging |
| **Single request/response messages** | One input object, one output object |
| **Enforce idempotency** | Code as if it might execute 100 times |
| **One mutation per activity** (writes) | For reads, accumulate data liberally into a single response |
| **Interface compatibility** | Inputs NOT in history (safe to change); outputs ARE (impact determinism) |
| **Non-retryable error ownership** | Prefer Workflow as retry policy owner; Activity only for truly terminal errors |
| **Prefer ScheduleToCloseTimeout** | Users care about latency, not retry count |
| **Constrain resource lifetimes** | Use `StartToCloseTimeout` to prevent Activity "zombies" |
| **Heartbeat for > 2 min** | Enables cancellation detection and checkpoint resumption |
| **Rate limiting** | Use `TaskQueueActivitiesPerSecond` on Worker to protect downstream |

**Activity Options**: See [workflow-reference.md](workflow-reference.md#activity-options) for `ActivityOptions` with `RetryPolicy` code example.

---

## Worker Configuration

### Basic Setup

```csharp
using var worker = new TemporalWorker(client,
    new TemporalWorkerOptions("my-task-queue")
        .AddWorkflow<OrderWorkflow>()
        .AddAllActivities<OrderActivities>());
await worker.ExecuteAsync(cancellationToken);
```

| Rule | Details |
|------|---------|
| **Isolate workloads** | Separate workers for workflows vs. expensive activities |
| **Scale horizontally** | Many small instances > few large ones |
| **Deadlock detection** | Handlers must yield within 1 second; use `TEMPORAL_DEBUG=1` for breakpoints |

### Wrapper Library Worker Pattern

```csharp
builder.AddHostedTemporalWorker(
    appSectionName: "MyApp",
    taskQueue: TaskQueueId.OrderFulfillmentCoordinator,
    buildId: BuildId.V1_0_0)
.ConfigureOptions(o => o.AddNexusService(new OrderNexusService()))
.AddWorkflow<OrderWorkflow>()
.AddSingletonActivities<IValidateActivities>()
.AddScopedActivities<ITriggerOaoActivities>();
```

> Register DI services separately: `builder.Services.AddScoped<IValidateActivities, ValidatedActivities>();`

**Full registration details**: See [configuration-reference.md](configuration-reference.md#worker-registration) for overloads, activity registration methods, and auto-configuration.

---

## Client Usage

### Starting Workflows

```csharp
var handle = await client.StartWorkflowAsync(
    (OrderWorkflow wf) => wf.RunAsync(request),
    new WorkflowOptions { Id = $"order-{orderId}", TaskQueue = "my-task-queue" });
```

### Workflow ID Strategies

| Policy | Use When |
|--------|----------|
| **WorkflowIdConflictPolicy.Fail** (default) | Explicit duplicate prevention with caller error handling |
| **WorkflowIdConflictPolicy.UseExisting** | Idempotent starts — retry safety and deduplication |
| **WorkflowIdReusePolicy.RejectDuplicate** | Prevents corruption from re-running steps |
| **WorkflowIdReusePolicy.AllowDuplicateFailedOnly** | **Production default** — allows "do over" of failed processes only |

> Use both `WorkflowIdConflictPolicy` (running) and `WorkflowIdReusePolicy` (completed) together for complete lifecycle control.

### Update-with-Start

```csharp
var startOp = WithStartWorkflowOperation.Create<IOrderWorkflow>(
    wf => wf.RunAsync(input), workflowOptions);
await client.ExecuteUpdateWithStartWorkflowAsync<IOrderWorkflow>(
    wf => wf.PlacedOrderUpdate(updateInput), new WorkflowUpdateWithStartOptions(startOp));
```

**Client registration examples**: See [configuration-reference.md](configuration-reference.md#client-registration) for `AddTemporalClient`, keyed services, and settings binding.

---

## Nexus Services

Cross-namespace RPC-style communication between Temporal workflows.

**When to Use**: Cross-namespace workflow communication, exposing workflows as service contracts, team autonomy with clear boundaries. **Not for**: Same-namespace (use child workflows) or simple data queries (use queries).

**Key patterns**:
- Three-method testability pattern: factory → `[ExcludeFromCodeCoverage]` handler → `protected internal virtual` Execute
- Namespace reference: `NexusRpc` for contracts, `NexusRpc.Handlers` + `Temporalio.Nexus` for handlers

**Full reference**: See [nexus-reference.md](nexus-reference.md) for handler patterns, context propagation, testing, and troubleshooting.

---

## Testing

### Critical Constraint: Non-Virtual SDK Methods

| ❌ Cannot Mock (Non-Virtual) | ✅ Mock This Instead (Virtual) |
|------------------------------|-------------------------------|
| `handle.ExecuteUpdateAsync(wf => ...)` | `handle.StartUpdateAsync<T>("MethodName", args, options)` |
| `handle.QueryAsync(wf => ...)` | `handle.QueryAsync<T>("QueryName", args, options)` |
| `handle.SignalAsync(wf => ...)` | `handle.SignalAsync("SignalName", args, options)` |

**Key Rule**: Production code uses expression-based methods. Tests must mock string-based virtual methods underneath.

### Test Decision Matrix

| Scenario | Unit Test | Integration Test |
|----------|-----------|------------------|
| Activity logic | ✅ Mock dependencies | ✅ With real services |
| Query/Signal/Update callers | ✅ Mock `WorkflowHandle<T>` | ✅ Full workflow |
| Nexus handler logic | ✅ Three-method pattern (Spy) | ✅ `CreateNexusEndpointAsync` |
| Update-with-start | ✅ `.Callback()` + expression capture | ✅ Recommended |
| Timer/delay behavior | ❌ | ✅ Time-skipping env |
| Workflow orchestration | ❌ | ✅ Required |
| Backward compatibility | ❌ | ✅ Replay tests |

**Full reference**: See [testing-reference.md](testing-reference.md) for all 7 mock patterns, integration testing, replay tests, and verification checklist.

> **Protobuf `Value` fields in test data**: JSON files cannot populate `Value` fields (`KindCase.None`). Construct objects programmatically and use `.ToProtoBufValueFromClassInput()` — see [protobuf-value-testing.md](/docs/procedures/protobuf-value-testing.md).

---

## Protobuf Contracts

Recommended for all workflow/activity contracts. Version under `/v1/`, `/v2/` dirs. Use `optional` for nullable fields. Never modify generated files — use partial classes.

**Schema evolution**: Add fields (safe), deprecate (safe), rename (risky for JSON), remove (risky), change type/cardinality (breaking), reuse field number (never). Always run Replay tests.

**Full reference**: See [protobuf-reference.md](protobuf-reference.md) for schema structure, evolution rules, project layout, and constants patterns.

---

## Timers & Delays

| Rule | Details |
|------|---------|
| **No Infinite ↔ real value changes** | Changing to/from `Infinite`/`InfiniteTimeSpan` is **non-deterministic** (NDE) |
| **Zero delay = 1ms timer** | `DelayAsync(TimeSpan.Zero)` creates a 1ms server-side timer in .NET |
| **Guard dynamic durations** | Validate durations from Activities/input before using in timers |
| **Add jitter** | Prevent Million Timers Issue when scheduling across many workflows |
| **Configurable for testing** | Accept durations as `ExecutionOptions` input |

**Code examples**: See [workflow-reference.md](workflow-reference.md#timers--delays).

---

## Messaging & Signals/Updates

**Signals**: ~few/sec sustained throughput. ALL signals contribute to event history, even unhandled — don't pipe unfiltered webhooks. Temporal won't drop signals, even during Closing.

**Updates**: Validator (`[WorkflowUpdateValidator]`) MUST NOT make external calls. Updates block a workflow slot — keep fast or use `WaitConditionAsync`.

**Propose/Apply Pattern**: When handlers need side effects, set state in handler (propose), execute side effects in main workflow method (apply). This avoids concurrency issues from blocking inside handlers.

**Queries**: Require Workers running; only work for Open/un-purged Closed workflows.
**Search Attributes**: Eventually consistent — NOT for customer-facing search. Values bypass DataConverter.

**Detailed patterns**: See [workflow-reference.md](workflow-reference.md#messaging--signalsupdates) for code examples.

---

## Versioning & Deployment

| Strategy | Use When |
|----------|----------|
| **Patched** (`Workflow.Patched("id")`) | Simple changes; callers don't need updating |
| **Routed** (TaskQueue/WorkflowType) | Complex changes; team controls callers and workers |
| **ContinueAsNew** | Preventing unbounded event history |

**Critical rules**: `changeId` is immutable (renaming causes NDE). Wait for retention period before removing old code blocks. Prefer additive schema changes. Activity inputs are NOT in history (safe); outputs ARE.

**Full strategies**: See [workflow-reference.md](workflow-reference.md#versioning--deployment) for Patched guidance, Routed variants, and schema versioning.

> **Modifying running workflows?** Use the `temporal-versioning` skill for complete versioning guidance: 3-step patching lifecycle, breaking changes checklist, workflow cutovers, non-determinism error recovery, and deployment verification checklists.

---

## Configuration

See [configuration-reference.md](configuration-reference.md) for `TemporalSettings`, `appsettings.json` structure, multi-client config, cloud/local setup, observability, and testing utilities.

**Key points**: Hierarchical binding (`shared:TemporalSettings` + `AppName:TemporalSettings`) is a common pattern. API key auto-enables TLS. Use the official SDK connection APIs directly, or wrapper helpers such as `AddTemporalClient` / `AddKeyedTemporalClient` if your organization provides them.

---

## Quick Reference: Temporal Attributes

| Attribute | Purpose |
|-----------|---------|
| `[Workflow]` | Marks class/interface as workflow |
| `[WorkflowRun]` | Main workflow entry point (one per workflow) |
| `[WorkflowUpdate]` | Handler for updates (request/response) |
| `[WorkflowQuery]` | Handler for queries (read-only) |
| `[WorkflowSignal]` | Handler for signals (fire-and-forget) |
| `[Activity]` | Marks method as activity |
| `[NexusService]` / `[NexusOperation]` | Nexus service contract |
| `[NexusServiceHandler]` / `[NexusOperationHandler]` | Nexus handler implementation |

---

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Non-deterministic workflow code | Use `Workflow.*` APIs for time, random, delays |
| Logging in workflows | **Never use `Workflow.Logger`, `ILogger`, or `LoggerMessage` in workflow code.** .NET logging providers use async I/O / background threads that cause NDE during replay. Capture context in state; log from activities only |
| Blocking I/O in workflows | Move to activities |
| Random workflow IDs | Use business-meaningful IDs via `NamingRules` helper |
| Mocking non-virtual SDK methods | Use string-based virtual method overloads |
| Modifying generated protobuf files | Use partial classes or extension methods |
| Installing or omitting packages blindly | Use the official `Temporalio` package directly, or confirm your wrapper library supplies the required dependencies |
| Using ad-hoc keyed DI for clients | Prefer a tested registration helper or an explicit client factory abstraction |
| Inline Nexus lambdas | Extract to private async methods for testability |
| Missing heartbeat for long activities | Add heartbeat if StartToCloseTimeout > 2 min |
| Deadlock in workflow handlers | Handlers must yield within 1 second |
| Configuring OTel inside workflow code or hidden library internals | Configure OpenTelemetry in your application's observability stack and connect it via interceptors |
| Wrong config section path | Use `shared:TemporalSettings` + `AppName:TemporalSettings` hierarchy |
| Calling activities via concrete class | Use interface-based `ExecuteActivityAsync<IInterface, TResult>` |
| Hardcoded task queues or build IDs | Use `TaskQueueId` and `BuildId` constants classes |
| Workflow exits before handlers finish | Use `Workflow.AllHandlersFinished` to wait |
| Using `CancelAsync()` in workflows | Non-deterministic — use synchronous `Cancel()` + `Dispose()` |
| Missing `IDisposable` with CTS fields | Workflows owning `CancellationTokenSource` fields must implement `IDisposable` |
| Not detecting cancellation | Use `TemporalException.IsCanceledException(e)` |
| Activity ignoring shutdown | Link `CancellationToken` + `WorkerShutdownToken` |
| Throwing exceptions for business failures | Capture in state + search attributes |
| Leaking Activity errors to callers | Catch and transform inside workflow |
| Callers setting workflow timeouts | Workflows own lifecycle via `ExecutionOptions` |
| Using `Workflow.Info.StartTime` for elapsed time | Pass timestamp as input |
| Blocking inside signal/update handlers | Use Propose/Apply pattern |
| Changing timer to/from Infinite | Non-deterministic — causes NDE |
| Unguarded dynamic timer durations | Validate before using in `DelayAsync` |
| Schema breaking changes in proto | Additive changes; never reuse field numbers; Replay tests |
| Renaming Patched `changeId` | Immutable — renaming causes NDE |
| Unbounded event history | ContinueAsNew; frequency driven by deploy cadence |
| Search Attributes for customer search | Eventually consistent — use proper storage |
| Piping unfiltered signals to workflow | All signals contribute to history — filter at caller |
| Local activities with no `RetryPolicy` | **Default = unlimited retries.** Deterministic failures (mapping, validation) retry forever silently. Always set `MaximumAttempts = 1` for local activities that perform pure transformations |
