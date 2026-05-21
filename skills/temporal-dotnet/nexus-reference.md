# Nexus Reference — Temporal .NET

Comprehensive reference for implementing Nexus services in Temporal .NET. Supplements the main SKILL.md with detailed patterns, context propagation, and troubleshooting.

> **Tip**: For Nexus questions not covered here, use the `mcp_temporal-docs_search_temporal_knowledge_sources` tool (if available) to search official Temporal documentation.

## Contents

- [Namespace Confusion](#namespace-confusion-nexusrpc-vs-nexusrpchandlers-vs-temporalionexus) — Using statements, common errors
- [Handler Patterns](#handler-patterns) — Sync/Async operations, workflow-starting handlers
- [Three-Method Testability Pattern](#three-method-testability-pattern) — Factory, handler, execute
- [Worker Registration](#worker-registration) — Adding Nexus services to workers
- [Context Propagation](#context-propagation) — Headers, caller info, tracing
- [Troubleshooting](#troubleshooting) — Common errors and fixes

---

## Namespace Confusion: NexusRpc vs NexusRpc.Handlers vs Temporalio.Nexus

The single most common source of errors is importing the wrong namespace.

### Using Statement Reference

| File Type | Required Usings | Purpose |
|-----------|----------------|---------|
| **Service contract** (`IMyNexusService.cs`) | `using NexusRpc;` | `[NexusService]`, `[NexusOperation]` |
| **Service handler** (`MyNexusService.cs`) | `using NexusRpc.Handlers;` + `using Temporalio.Nexus;` | Handler attributes + execution context |
| **Caller workflow** (`CallerWorkflow.cs`) | `using Temporalio.Workflows;` + `using Temporalio.Nexus;` | `Workflow.CreateNexusClient<T>()` |

### Common Errors from Wrong Namespace

| Error | Cause | Fix |
|-------|-------|-----|
| `OperationHandler` not found | Missing `using NexusRpc.Handlers;` | Add handler using |
| `NexusOperationExecutionContext` not found | Missing `using Temporalio.Nexus;` | Add Temporalio.Nexus using |
| `[NexusServiceHandler]` not found | Using `NexusRpc` instead of `NexusRpc.Handlers` | Switch to handlers namespace |
| `Workflow.CreateNexusClient<T>()` not found | Missing `using Temporalio.Nexus;` | Extension method lives in Temporalio.Nexus |

---

## Handler Patterns

### Sync Handler (Most Common)

Returns a result directly from within the handler. Best for operations that query existing workflows or perform quick lookups.

```csharp
[NexusServiceHandler(typeof(IMyNexusService))]
public class MyNexusService
{
    [NexusOperationHandler]
    public IOperationHandler<GetOrderInput, GetOrderOutput> GetOrder() =>
        OperationHandler.Sync<GetOrderInput, GetOrderOutput>(HandleGetOrderAsync);

    [ExcludeFromCodeCoverage]
    private async Task<GetOrderOutput> HandleGetOrderAsync(
        OperationStartContext context, GetOrderInput input)
    {
        var execCtx = NexusOperationExecutionContext.Current;
        var client = execCtx.TemporalClient;
        var logger = execCtx.Logger;

        return await ExecuteGetOrderAsync(client, logger, input);
    }

    protected internal virtual async Task<GetOrderOutput> ExecuteGetOrderAsync(
        ITemporalClient client, ILogger logger, GetOrderInput input)
    {
        var handle = client.GetWorkflowHandle<IOrderWorkflow>(input.OrderId, null, null);
        var state = await handle.QueryAsync<OrderState>("GetOrderState", Array.Empty<object?>(), null);
        return new GetOrderOutput(state);
    }
}
```

### Async (Workflow-Backed) Handler

Starts a workflow and returns when the workflow completes. Best for operations that are long-running or need durability.

```csharp
[NexusOperationHandler]
public IOperationHandler<CreateOrderInput, CreateOrderOutput> CreateOrder() =>
    WorkflowRunOperationHandler.FromHandleFactory(
        (WorkflowRunOperationContext context, CreateOrderInput input) =>
            context.StartWorkflowAsync(
                (OrderWorkflow wf) => wf.RunAsync(input),
                new()
                {
                    Id = context.HandlerContext.RequestId,
                    // Use RequestId for idempotent workflow starts
                }));
```

Note: Return type of workflow must match the output type (`CreateOrderOutput`).

### Handler with Update-and-Start

```csharp
[NexusOperationHandler]
public IOperationHandler<PlaceOrderInput, PlaceOrderOutput> PlaceOrder() =>
    OperationHandler.Sync<PlaceOrderInput, PlaceOrderOutput>(HandlePlaceOrderAsync);

private async Task<PlaceOrderOutput> HandlePlaceOrderAsync(
    OperationStartContext context, PlaceOrderInput input)
{
    var execCtx = NexusOperationExecutionContext.Current;
    var client = execCtx.TemporalClient;

    var startOp = WithStartWorkflowOperation.Create<IOrderWorkflow>(
        wf => wf.RunAsync(input.OrderRequest),
        new()
        {
            Id = $"order-{input.OrderId}",
            TaskQueue = "order-queue",
            IdConflictPolicy = WorkflowIdConflictPolicy.UseExisting,
        });

    var updateResult = await client.ExecuteUpdateWithStartWorkflowAsync<IOrderWorkflow>(
        wf => wf.PlacedOrderUpdate(input.UpdateRequest),
        new WorkflowUpdateWithStartOptions(startOp));

    return updateResult;
}
```

---

## Three-Method Testability Pattern

This is the **key pattern** for making Nexus handlers unit-testable:

```
┌─────────────────────────────────────────┐
│ 1. [NexusOperationHandler]              │  Public factory (wiring only)
│    Returns OperationHandler.Sync<>()    │
├─────────────────────────────────────────┤
│ 2. [ExcludeFromCodeCoverage]            │  Extracts context, delegates
│    private HandleXxxAsync()             │  Gets TemporalClient + Logger
│    Gets TemporalClient from context     │
├─────────────────────────────────────────┤
│ 3. protected internal virtual           │  Testable business logic
│    ExecuteXxxAsync(client, logger,      │  Override in test subclass
│                    input)               │
└─────────────────────────────────────────┘
```

### Full Example

```csharp
[NexusServiceHandler(typeof(IOrderNexusService))]
public class OrderNexusService
{
    // Layer 1: Factory (not testable directly)
    [NexusOperationHandler]
    public IOperationHandler<GetOrderInput, GetOrderOutput> GetOrder() =>
        OperationHandler.Sync<GetOrderInput, GetOrderOutput>(HandleGetOrderAsync);

    // Layer 2: Context extraction (not testable — mark [ExcludeFromCodeCoverage])
    [ExcludeFromCodeCoverage]
    private async Task<GetOrderOutput> HandleGetOrderAsync(
        OperationStartContext context, GetOrderInput input)
    {
        var execCtx = NexusOperationExecutionContext.Current;
        return await ExecuteGetOrderAsync(
            execCtx.TemporalClient, execCtx.Logger, input);
    }

    // Layer 3: Testable logic (accepts ITemporalClient + ILogger)
    protected internal virtual async Task<GetOrderOutput> ExecuteGetOrderAsync(
        ITemporalClient client, ILogger logger, GetOrderInput input)
    {
        var handle = client.GetWorkflowHandle<IOrderWorkflow>(input.OrderId, null, null);
        var state = await handle.QueryAsync<OrderState>("GetOrderState", Array.Empty<object?>(), null);
        return new GetOrderOutput(state);
    }
}
```

### Test Class

```csharp
public class OrderNexusServiceTests
{
    // Testable subclass exposes protected internal methods
    private sealed class TestableOrderNexusService : OrderNexusService
    {
        public Task<GetOrderOutput> TestGetOrder(
            ITemporalClient client, ILogger logger, GetOrderInput input)
            => ExecuteGetOrderAsync(client, logger, input);
    }

    private readonly Mock<ITemporalClient> _clientMock = new(MockBehavior.Strict);
    private readonly Mock<ILogger<OrderNexusService>> _loggerMock = new();

    [Fact]
    public async Task GetOrder_ReturnsOrderState()
    {
        // Arrange
        var workflowHandle = new Mock<WorkflowHandle<IOrderWorkflow>>(
            _clientMock.Object, "order-123", null, null, null);

        workflowHandle.Setup(x => x.QueryAsync<OrderState>(
            "GetOrderState",
            It.IsAny<IReadOnlyCollection<object?>>(),
            It.IsAny<WorkflowQueryOptions>()))
            .ReturnsAsync(new OrderState { Status = "Active" });

        _clientMock.Setup(x => x.GetWorkflowHandle<IOrderWorkflow>("order-123", null, null))
            .Returns(workflowHandle.Object);

        var service = new TestableOrderNexusService();

        // Act
        var result = await service.TestGetOrder(
            _clientMock.Object, _loggerMock.Object, new GetOrderInput("order-123"));

        // Assert
        Assert.Equal("Active", result.State.Status);
    }
}
```

---

## Worker Registration

### Registering Nexus Services

```csharp
// Standard SDK pattern
var worker = new TemporalWorker(client,
    new TemporalWorkerOptions("my-task-queue")
        .AddNexusService(new OrderNexusService())
        .AddWorkflow<OrderWorkflow>());

// Example wrapper-library pattern with hosted worker
builder.AddHostedTemporalWorker(taskQueue: "my-task-queue", builderId: "order-worker")
    .ConfigureOptions(o =>
    {
        o.AddNexusService(new OrderNexusService());
    })
    .AddWorkflow<OrderWorkflow>();
```

### Task Queue Separation

```
┌─────────────────┐     ┌──────────────────────┐
│ Caller Worker    │     │ Handler Worker        │
│ TQ: caller-queue │────▶│ TQ: handler-queue     │
│ Workflows only   │     │ Nexus + Workflows     │
└─────────────────┘     └──────────────────────┘
```

Nexus endpoint binds to the handler worker's task queue. Caller workflow uses `Workflow.CreateNexusClient<T>("endpoint-name")`.

---

## Context Propagation

### Interceptor Pattern for Correlation IDs

```csharp
public class CorrelationInterceptor : IWorkerInterceptor
{
    public WorkflowInboundInterceptor InterceptWorkflow(
        WorkflowInboundInterceptor nextInterceptor) =>
        new CorrelationWorkflowInterceptor(nextInterceptor);
}

public class CorrelationWorkflowInterceptor : WorkflowInboundInterceptor
{
    public CorrelationWorkflowInterceptor(WorkflowInboundInterceptor next) : base(next) { }

    public override void Init(WorkflowOutboundInterceptor outbound)
    {
        base.Init(new CorrelationOutboundInterceptor(outbound));
    }
}

public class CorrelationOutboundInterceptor : WorkflowOutboundInterceptor
{
    public CorrelationOutboundInterceptor(WorkflowOutboundInterceptor next) : base(next) { }

    public override Task<TResult> StartNexusOperationAsync<TResult>(
        StartNexusOperationInput input)
    {
        // Add correlation headers to Nexus calls
        input.Headers["x-correlation-id"] = Workflow.Info.WorkflowId;
        return base.StartNexusOperationAsync<TResult>(input);
    }
}
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `NexusOperationExecutionContext.Current` throws | Calling outside Nexus handler context | Only access within handler methods |
| "No handler registered" | Missing `AddNexusService()` on worker | Add to worker options |
| "Endpoint not found" | Endpoint name mismatch or not created | Verify endpoint name matches exactly |
| Cannot mock `NexusOperationExecutionContext.Current` | Static context, not mockable | Use three-method testability pattern |
| Handler methods not found | Wrong attribute namespace | Verify `NexusRpc.Handlers` for handler attributes |
| `CreateNexusClient<T>` not found | Missing Temporalio.Nexus using | Add `using Temporalio.Nexus;` in workflow |
| Nexus call times out | Handler worker not running or wrong task queue | Verify handler worker is up and task queue matches endpoint config |
