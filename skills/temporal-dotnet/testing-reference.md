# Testing Reference — Temporal .NET

Complete reference for unit and integration testing of Temporal workflows, activities, Nexus services, and client interactions. Supplements the main SKILL.md.

> **Tip**: For testing questions not covered here, use the `mcp_temporal-docs_search_temporal_knowledge_sources` tool (if available) to search official Temporal documentation.

## Contents

- [Testing Foundations](#testing-foundations) — Verification styles, test doubles, isolation decisions
- [SDK Method Mocking Reference](#sdk-method-mocking-reference) — Non-virtual constraint table, exact signatures
- [Pattern 1: Testing Update Operations](#pattern-1-testing-update-operations) — Includes void update variant
- [Pattern 2: Testing Query Operations](#pattern-2-testing-query-operations) — Includes exception-then-query fallback
- [Pattern 3: Testing Signal Operations](#pattern-3-testing-signal-operations)
- [Pattern 4: Testing Workflow Existence Check](#pattern-4-testing-workflow-existence-check)
- [Pattern 5: Testing Exception Handling](#pattern-5-testing-exception-handling) — RpcException status codes
- [Pattern 6: Nexus Handler Testing](#pattern-6-nexus-handler-testing-three-method-pattern)
- [Pattern 7: Update-with-Start Testing](#pattern-7-update-with-start-testing) — Expression capture, argument validation
- [Common Mistakes](#common-mistakes) — ❌/✅ anti-pattern pairs
- [Activity Testing](#activity-testing)
- [Test Setup Patterns](#test-setup-patterns) — Keyed services, controller/service initialization
- [Helper Utilities](#helper-utilities) — ExtractArgumentValues, AsyncEnumerable helpers
- [Integration Testing](#integration-testing) — **Time-skipping vs Local server choice**, BaseWorkflowEnvironment, Nexus integration
- [Local Activity Retry Behavior Tests](#local-activity-retry-behavior-tests) — Proving default infinite retry and MaximumAttempts=1 fix
- [Test Decision Matrix](#test-decision-matrix)
- [Verification Checklist](#verification-checklist)

---

## Testing Foundations

### Verification Styles

Understand the distinction between **state** and **behavior** verification:

- **State verification**: Assert on workflow _result_, _Query_ response, _Update_ response, or _SearchAttribute_ value after execution
- **Behavior verification**: Assert that specific Activities were called with expected arguments in expected order. Most workflows require this since steps commonly receive inputs based on previous steps

> Returning a `result` from a Workflow couples callers to that contract and can cause maintenance issues. Prefer Query-based state verification when possible.

### Test Doubles (Meszaros taxonomy)

| Type | Definition | Temporal Use |
|------|-----------|--------------|
| **Dummy** | Passed around, never used | Fill parameter lists in constructors |
| **Fake** | Working implementation, not production-suitable | `FakeNexusServiceHandler` for cross-namespace calls |
| **Stub** | Canned answers for specific calls | Activity mock returning fixed data |
| **Spy** | Stub that records call info | `OrderNexusServiceSpy` (testable subclass) |
| **Mock** | Pre-programmed expectations | `Mock<ITemporalClient>(MockBehavior.Strict)` |

### Activity Test Isolation Decision

> Should I test my Activities in isolation?

| Condition | Recommendation |
|-----------|----------------|
| Activity is a thin Adapter that just transforms input for Temporal | Skip isolation test — ceremonial/useless |
| Activity has complex algorithm (that doesn't belong in its dependency) | Test in isolation |
| Activity interacts with `ActivityExecutionContext` (heartbeats, timeouts) | Test with `ActivityEnvironment` |

### Workflow Test Isolation Boundary

> Should Activities be mocked, or their _inner dependencies_?

| Condition | Mock Boundary | Style |
|-----------|--------------|-------|
| Not maintaining separate Activity tests | Mock dependencies _inside_ Activities | "Blackbox" — Activity is an adapter belonging to the workflow definition |
| Already invested in dependency mocks elsewhere | Mock dependencies _inside_ Activities | Reuse existing mocks |
| Workflow has conditional branches | Mock Activities directly (return fixed results) | Reduces test complexity for branch verification |

---

## SDK Method Mocking Reference

### Critical: Virtual vs Non-Virtual Methods

The Temporal .NET SDK uses expression-based extension methods that are **non-virtual** and cannot be mocked. You must mock the underlying string-based virtual methods.

| Category | ❌ Non-Virtual (Production) | ✅ Virtual (Mock This) |
|----------|---------------------------|----------------------|
| **Update** | `handle.ExecuteUpdateAsync(wf => wf.Method(args))` | `handle.StartUpdateAsync<TResult>("MethodName", args, options)` + `updateHandle.GetResultAsync<TResult>(options)` |
| **Query** | `handle.QueryAsync(wf => wf.Method(args))` | `handle.QueryAsync<TResult>("MethodName", args, options)` |
| **Signal** | `handle.SignalAsync(wf => wf.Method(args))` | `handle.SignalAsync("MethodName", args, options)` |
| **Start** | `client.StartWorkflowAsync(wf => wf.Run(args), opts)` | `client.StartWorkflowAsync("WorkflowName", args, opts)` — but expression version IS virtual |
| **Execute** | `client.ExecuteWorkflowAsync(wf => wf.Run(args), opts)` | Usually virtual — verify in SDK source |

### Constructor Parameters for Mock Objects

```csharp
// ITemporalClient — mock interface directly
var clientMock = new Mock<ITemporalClient>();

// WorkflowHandle<T> — 5 parameters
var workflowHandle = new Mock<WorkflowHandle<IMyWorkflow>>(
    clientMock.Object,  // ITemporalClient
    "workflow-id",      // string workflowId
    null,               // string? runId
    null,               // string? firstExecutionRunId
    null);              // string? resultRunId

// WorkflowUpdateHandle<T> — 4 parameters
var updateHandle = new Mock<WorkflowUpdateHandle<MyResponse>>(
    clientMock.Object,  // ITemporalClient
    "update-id",        // string updateId
    "workflow-id",      // string workflowId
    null);              // string? workflowRunId

// Non-generic WorkflowUpdateHandle — for void updates (no TResult)
var voidUpdateHandle = new Mock<WorkflowUpdateHandle>(
    clientMock.Object,  // ITemporalClient
    "update-id",        // string updateId
    "workflow-id",      // string workflowId
    null);              // string? workflowRunId
```

### Exact Virtual Method Signatures (from temporalio/sdk-dotnet)

Copy-pasteable signatures for setting up mocks:

```csharp
// ✅ VIRTUAL — Mock this for updates (on WorkflowHandle<TWorkflow>)
public virtual Task<WorkflowUpdateHandle<TResult>> StartUpdateAsync<TResult>(
    string update,
    IReadOnlyCollection<object?> args,
    WorkflowUpdateStartOptions? options = null);

// ✅ VIRTUAL — Mock this for queries (on WorkflowHandle<TWorkflow>)
public virtual Task<TResult> QueryAsync<TResult>(
    string query,
    IReadOnlyCollection<object?> args,
    WorkflowQueryOptions? options = null);

// ✅ VIRTUAL — Mock this for signals (on WorkflowHandle<TWorkflow>)
public virtual Task SignalAsync(
    string signal,
    IReadOnlyCollection<object?> args,
    WorkflowSignalOptions? options = null);

// ✅ VIRTUAL — Mock this for update-with-start (on ITemporalClient)
public virtual Task<WorkflowUpdateHandle<TResult>> StartUpdateWithStartWorkflowAsync<TWorkflow, TResult>(
    Expression<Func<TWorkflow, Task<TResult>>> updateStartWorkflowActionExpr,
    WorkflowStartUpdateWithStartOptions options);
```

**Non-virtual extension methods (CANNOT mock):**

```csharp
// ❌ Extension method on WorkflowHandle — delegates to StartUpdateAsync + GetResultAsync
public static Task<TResult> ExecuteUpdateAsync<TWorkflow, TResult>(
    this WorkflowHandle<TWorkflow> handle,
    Expression<Func<TWorkflow, Task<TResult>>> updateStartWorkflowActionExpr,
    WorkflowUpdateOptions? options = null);

// ❌ Non-virtual overload on WorkflowHandle
public Task<TResult> QueryAsync<TResult>(
    Expression<Func<TWorkflow, TResult>> queryWorkflowExpr,
    WorkflowQueryOptions? options = null);

// ❌ Non-virtual overload on WorkflowHandle
public Task SignalAsync(
    Expression<Func<TWorkflow, Task>> signalWorkflowExpr,
    WorkflowSignalOptions? options = null);
```

---

## Pattern 1: Testing Update Operations

The most complex pattern due to the two-step mock requirement.

```csharp
[Fact]
public async Task ProcessOrder_ReturnsExpectedResponse()
{
    // Arrange
    var clientMock = new Mock<ITemporalClient>();
    var expectedResponse = new OrderResponse { Status = "Processed" };

    // Step 1: Mock update handle with result
    var updateHandle = new Mock<WorkflowUpdateHandle<OrderResponse>>(
        clientMock.Object, "update-id", "order-123", null);
    updateHandle.Setup(x => x.GetResultAsync<OrderResponse>(
            It.IsAny<RpcOptions?>()))
        .ReturnsAsync(expectedResponse);

    // Step 2: Mock workflow handle to return update handle
    var workflowHandle = new Mock<WorkflowHandle<IOrderWorkflow>>(
        clientMock.Object, "order-123", null, null, null);
    workflowHandle.Setup(x => x.StartUpdateAsync<OrderResponse>(
            "ProcessOrder",  // ← String method name, NOT expression
            It.IsAny<IReadOnlyCollection<object?>>(),
            It.IsAny<WorkflowUpdateStartOptions>()))
        .ReturnsAsync(updateHandle.Object);

    // Step 3: Wire client → workflow handle
    clientMock.Setup(x => x.GetWorkflowHandle<IOrderWorkflow>("order-123", null, null))
        .Returns(workflowHandle.Object);

    var sut = new OrderService(clientMock.Object);

    // Act
    var result = await sut.ProcessOrderAsync("order-123", new OrderInput());

    // Assert
    Assert.Equal("Processed", result.Status);
}
```

### Void Update Variant (ValueTuple)

When the update method returns `Task` (not `Task<T>`), use `ValueTuple` as the result type:

```csharp
[Fact]
public async Task PlaceOrder_VoidUpdate_Succeeds()
{
    // Arrange
    var clientMock = new Mock<ITemporalClient>();

    // Non-generic WorkflowUpdateHandle for void updates
    var updateHandle = new Mock<WorkflowUpdateHandle>(
        clientMock.Object, "update-id", "order-123", null);
    updateHandle.Setup(x => x.GetResultAsync<ValueTuple>(It.IsAny<RpcOptions?>()))
        .ReturnsAsync(default(ValueTuple));

    var workflowHandle = new Mock<WorkflowHandle<IOrderWorkflow>>(
        clientMock.Object, "order-123", null, null, null);
    workflowHandle.Setup(x => x.StartUpdateAsync<ValueTuple>(
            "PlaceOrder",
            It.IsAny<IReadOnlyCollection<object?>>(),
            It.IsAny<WorkflowUpdateStartOptions>()))
        .ReturnsAsync(updateHandle.Object);

    clientMock.Setup(x => x.GetWorkflowHandle<IOrderWorkflow>("order-123", null, null))
        .Returns(workflowHandle.Object);

    var sut = new OrderService(clientMock.Object);

    // Act & Assert — no exception = success
    await sut.PlaceOrderAsync("order-123", new OrderInput());
}
```

> **Key**: Use `WorkflowUpdateHandle` (non-generic) and `GetResultAsync<ValueTuple>()` returning `default(ValueTuple)` for updates that return `Task`.

---

## Pattern 2: Testing Query Operations

```csharp
[Fact]
public async Task GetOrderState_ReturnsCurrentState()
{
    // Arrange
    var clientMock = new Mock<ITemporalClient>();
    var expectedState = new OrderState { Status = "Active" };

    var workflowHandle = new Mock<WorkflowHandle<IOrderWorkflow>>(
        clientMock.Object, "order-123", null, null, null);
    workflowHandle.Setup(x => x.QueryAsync<OrderState>(
            "GetOrderState",  // ← String method name
            It.IsAny<IReadOnlyCollection<object?>>(),
            It.IsAny<WorkflowQueryOptions>()))
        .ReturnsAsync(expectedState);

    clientMock.Setup(x => x.GetWorkflowHandle<IOrderWorkflow>("order-123", null, null))
        .Returns(workflowHandle.Object);

    var sut = new OrderQueryService(clientMock.Object);

    // Act
    var result = await sut.GetOrderStateAsync("order-123");

    // Assert
    Assert.Equal("Active", result.Status);
}
```

### Exception-Then-Query Fallback

Common pattern: attempt an update, catch "workflow execution already completed", fall back to query:

```csharp
[Fact]
public async Task GetStatus_WhenWorkflowCompleted_FallsBackToQuery()
{
    // Arrange
    var clientMock = new Mock<ITemporalClient>();
    var workflowState = new OrderState
    {
        Status = "Completed",
        LastUpdated = DateTime.UtcNow
    };

    // Step 1: Update handle throws "workflow execution already completed"
    var updateHandle = new Mock<WorkflowUpdateHandle<OrderResponse>>(
        clientMock.Object, "update-id", "order-123", null);
    updateHandle.Setup(x => x.GetResultAsync<OrderResponse>(It.IsAny<RpcOptions?>()))
        .ThrowsAsync(new RpcException(
            // Production uses StringComparison.OrdinalIgnoreCase for message matching
            RpcException.StatusCode.FailedPrecondition,
            "workflow execution already completed", null));

    var workflowHandle = new Mock<WorkflowHandle<IOrderWorkflow>>(
        clientMock.Object, "order-123", null, null, null);
    workflowHandle.Setup(x => x.StartUpdateAsync<OrderResponse>(
            "RefreshStatus",
            It.IsAny<IReadOnlyCollection<object?>>(),
            It.IsAny<WorkflowUpdateStartOptions>()))
        .ReturnsAsync(updateHandle.Object);

    // Step 2: Query returns final state (fallback path)
    workflowHandle.Setup(x => x.QueryAsync<OrderState>(
            "GetOrderState",
            It.IsAny<IReadOnlyCollection<object?>>(),
            It.IsAny<WorkflowQueryOptions>()))
        .ReturnsAsync(workflowState);

    clientMock.Setup(x => x.GetWorkflowHandle<IOrderWorkflow>("order-123", null, null))
        .Returns(workflowHandle.Object);

    var sut = new OrderService(clientMock.Object);

    // Act
    var result = await sut.GetStatusAsync("order-123");

    // Assert — result comes from query fallback, not update
    Assert.Equal("Completed", result.Status);
    workflowHandle.Verify(x => x.QueryAsync<OrderState>(
        "GetOrderState",
        It.IsAny<IReadOnlyCollection<object?>>(),
        It.IsAny<WorkflowQueryOptions>()), Times.Once);
}
```

> **Pattern**: Production code uses `try { ExecuteUpdateAsync(...) } catch (RpcException ex) when (ex.Message.Contains("workflow execution already completed", StringComparison.OrdinalIgnoreCase)) { QueryAsync(...) }`. Test both the update throw and the query fallback.

---

## Pattern 3: Testing Signal Operations

```csharp
[Fact]
public async Task CancelOrder_SendsSignalSuccessfully()
{
    // Arrange
    var clientMock = new Mock<ITemporalClient>();

    var workflowHandle = new Mock<WorkflowHandle<IOrderWorkflow>>(
        clientMock.Object, "order-123", null, null, null);
    workflowHandle.Setup(x => x.SignalAsync(
            "CancelOrder",  // ← String method name
            It.IsAny<IReadOnlyCollection<object?>>(),
            It.IsAny<WorkflowSignalOptions?>()))
        .Returns(Task.CompletedTask);

    clientMock.Setup(x => x.GetWorkflowHandle<IOrderWorkflow>("order-123", null, null))
        .Returns(workflowHandle.Object);

    var sut = new OrderService(clientMock.Object);

    // Act
    await sut.CancelOrderAsync("order-123", new CancelRequest());

    // Assert
    workflowHandle.Verify(x => x.SignalAsync(
        "CancelOrder",
        It.IsAny<IReadOnlyCollection<object?>>(),
        It.IsAny<WorkflowSignalOptions?>()), Times.Once);
}
```

---

## Pattern 4: Testing Workflow Existence Check

```csharp
[Fact]
public async Task IsWorkflowRunning_ReturnsTrueForActiveWorkflow()
{
    // Arrange
    var clientMock = new Mock<ITemporalClient>();

    var workflowHandle = new Mock<WorkflowHandle<IOrderWorkflow>>(
        clientMock.Object, "order-123", null, null, null);
    workflowHandle.Setup(x => x.DescribeAsync(It.IsAny<WorkflowDescribeOptions?>()))
        .ReturnsAsync(new WorkflowExecution.Description(/* ... */));

    clientMock.Setup(x => x.GetWorkflowHandle<IOrderWorkflow>("order-123", null, null))
        .Returns(workflowHandle.Object);

    var sut = new OrderService(clientMock.Object);

    // Act
    var result = await sut.IsRunningAsync("order-123");

    // Assert
    Assert.True(result);
}

[Fact]
public async Task IsWorkflowRunning_ReturnsFalseForMissingWorkflow()
{
    // Arrange
    var clientMock = new Mock<ITemporalClient>();

    var workflowHandle = new Mock<WorkflowHandle<IOrderWorkflow>>(
        clientMock.Object, "order-123", null, null, null);
    workflowHandle.Setup(x => x.DescribeAsync(It.IsAny<WorkflowDescribeOptions?>()))
        .ThrowsAsync(new RpcException(
            RpcException.StatusCode.NotFound, "not found", null));

    clientMock.Setup(x => x.GetWorkflowHandle<IOrderWorkflow>("order-123", null, null))
        .Returns(workflowHandle.Object);

    var sut = new OrderService(clientMock.Object);

    // Act
    var result = await sut.IsRunningAsync("order-123");

    // Assert
    Assert.False(result);
}
```

---

## Pattern 5: Testing Exception Handling

### RpcException Construction

`RpcException` constructor: `RpcException(RpcException.StatusCode statusCode, string message, RawValue? failure)`

Common status codes to test:

| Status Code | Scenario |
|-------------|----------|
| `NotFound` | Workflow doesn't exist |
| `FailedPrecondition` | Workflow already completed |
| `Internal` | Workflow execution failure |
| `Unavailable` | Temporal server unreachable |
| `DeadlineExceeded` | Operation timed out |

```csharp
[Fact]
public async Task ProcessOrder_ThrowsOnTemporalError()
{
    // Arrange
    var clientMock = new Mock<ITemporalClient>();

    var workflowHandle = new Mock<WorkflowHandle<IOrderWorkflow>>(
        clientMock.Object, "order-123", null, null, null);
    workflowHandle.Setup(x => x.StartUpdateAsync<OrderResponse>(
            "ProcessOrder",
            It.IsAny<IReadOnlyCollection<object?>>(),
            It.IsAny<WorkflowUpdateStartOptions>()))
        .ThrowsAsync(new RpcException(
            RpcException.StatusCode.Internal,
            "Workflow execution failed", null));

    clientMock.Setup(x => x.GetWorkflowHandle<IOrderWorkflow>("order-123", null, null))
        .Returns(workflowHandle.Object);

    var sut = new OrderService(clientMock.Object);

    // Act & Assert
    var ex = await Assert.ThrowsAsync<RpcException>(
        () => sut.ProcessOrderAsync("order-123", new OrderInput()));
    Assert.Equal(RpcException.StatusCode.Internal, ex.Code);
    Assert.Contains("Workflow execution failed", ex.Message);
}
```

### Skip Convention for Non-Testable Scenarios

When a scenario requires non-virtual SDK methods, mark the test as skipped:

```csharp
[Fact(Skip = "ExecuteUpdateWithStartWorkflowAsync cannot be fully unit tested. " +
             "See integration tests in OrderWorkflowIntegrationTests.cs")]
public async Task PlacedOrder_UpdateWithStart_Scenario() { }
```
```

---

## Pattern 6: Nexus Handler Testing (Three-Method Pattern)

See [nexus-reference.md](nexus-reference.md) for the full three-method testability pattern.

### Simplified Test Setup

```csharp
public class OrderNexusServiceTests : BaseUnitTestAddons
{
    private readonly Mock<ILogger<OrderNexusService>> _loggerMock = new();
    private readonly Mock<ITemporalClient> _temporalClientMock = new(MockBehavior.Strict);
    private readonly OrderNexusServiceSpy _sut = new();

    /// <summary>
    /// Testable wrapper — exposes protected internal methods.
    /// Follows SOP: minimal wrapper for accessibility only.
    /// </summary>
    private sealed class OrderNexusServiceSpy : OrderNexusService
    {
        public Task<GetOrderOutput> InvokeExecuteGetOrderAsync(
            ITemporalClient client, ILogger logger, GetOrderInput input)
            => ExecuteGetOrderAsync(client, logger, input);
    }

    [Fact]
    public async Task GetOrder_QueriesWorkflowState()
    {
        // Arrange
        var handle = new Mock<WorkflowHandle<IOrderWorkflow>>(
            _temporalClientMock.Object, "order-123", null, null, null);
        handle.Setup(x => x.QueryAsync<OrderState>(
                "GetOrderState",
                It.IsAny<IReadOnlyCollection<object?>>(),
                It.IsAny<RpcOptions?>()))
            .ReturnsAsync(new OrderState { Status = "Active" });

        _temporalClientMock
            .Setup(x => x.GetWorkflowHandle<IOrderWorkflow>("order-123", null, null))
            .Returns(handle.Object);

        // Act
        var result = await _sut.InvokeExecuteGetOrderAsync(
            _temporalClientMock.Object, _loggerMock.Object,
            new GetOrderInput("order-123"));

        // Assert
        Assert.Equal("Active", result.State.Status);
        VerifyMocks();
    }
}
```

---

## Pattern 7: Update-with-Start Testing

`StartUpdateWithStartWorkflowAsync` IS virtual and CAN be mocked. Use `.Callback()` to capture the expression and options for assertion.

```csharp
[Fact]
public async Task PlacedOrder_UpdateWithStart_CreatesWorkflowAndUpdates()
{
    // Arrange
    var clientMock = new Mock<ITemporalClient>();

    // Non-generic WorkflowUpdateHandle for void updates
    var updateHandle = new Mock<WorkflowUpdateHandle>(
        clientMock.Object, "update-id", $"order-{orderId}", null);
    updateHandle.Setup(x => x.GetResultAsync<ValueTuple>(It.IsAny<RpcOptions?>()))
        .ReturnsAsync(default(ValueTuple));

    // Capture expression and options for assertion
    var capturedExpression = default(Expression<Func<IOrderWorkflow, Task>>);
    var capturedOptions = default(WorkflowStartUpdateWithStartOptions);

    clientMock.Setup(m => m.StartUpdateWithStartWorkflowAsync(
            It.IsAny<Expression<Func<IOrderWorkflow, Task>>>(),
            It.IsAny<WorkflowStartUpdateWithStartOptions>()))
        .Callback<Expression<Func<IOrderWorkflow, Task>>, WorkflowStartUpdateWithStartOptions>(
            (expr, opts) =>
            {
                capturedExpression = expr;
                capturedOptions = opts;
            })
        .ReturnsAsync(updateHandle.Object);

    var sut = new OrderController(clientMock.Object);

    // Act
    var result = await sut.PutPlacedOrder(orderId, request, null);

    // Assert — verify the correct update method was called
    var methodCall = (MethodCallExpression)capturedExpression!.Body;
    Assert.Equal("PlacedOrderUpdate", methodCall.Method.Name);

    // Assert — verify arguments sent to workflow
    var arguments = ExtractArgumentValues.From(methodCall);
    Assert.Equal(expectedInput, arguments[0]);

    // Assert — verify workflow ID from StartWorkflowOperation.Options
    Assert.Equal($"order-{orderId}",
        capturedOptions!.StartWorkflowOperation?.Options?.Id);
}
```

### With Typed Return Value

When the update returns a response (not void):

```csharp
[Fact]
public async Task SubmitCart_ReturnsResponse()
{
    // Arrange
    var clientMock = new Mock<ITemporalClient>();
    var expectedResponse = new CartSubmitResponse { CartId = "cart-123" };

    var updateHandle = new Mock<WorkflowUpdateHandle<CartSubmitResponse>>(
        clientMock.Object, "update-id", "cart-123", null);
    updateHandle.Setup(x => x.GetResultAsync<CartSubmitResponse>(It.IsAny<RpcOptions?>()))
        .ReturnsAsync(expectedResponse);

    clientMock.Setup(x => x.StartUpdateWithStartWorkflowAsync(
            It.IsAny<Expression<Func<ICartWorkflow, Task<CartSubmitResponse>>>>(),
            It.IsAny<WorkflowStartUpdateWithStartOptions>()))
        .ReturnsAsync(updateHandle.Object);

    var sut = new CartService(clientMock.Object);

    // Act
    var result = await sut.SubmitCartAsync("cart-123", new CartInput());

    // Assert
    Assert.Equal("cart-123", result.CartId);
}
```

> **Key differences from Pattern 1**: Mock `StartUpdateWithStartWorkflowAsync` on `ITemporalClient` (not on `WorkflowHandle`). Use `.Callback()` to capture the expression for method name/argument validation. Expression type must match exactly: `Expression<Func<IWorkflow, Task>>` for void or `Expression<Func<IWorkflow, Task<TResult>>>` for typed.

---

## Common Mistakes

### ❌ Trying to mock ExecuteUpdateAsync (extension method)
```csharp
// THIS WILL FAIL — ExecuteUpdateAsync is an extension method, not mockable!
handleMock.Setup(x => x.ExecuteUpdateAsync(wf => wf.ProcessOrder(input)))
    .ReturnsAsync(response);
```

✅ **Fix**: Mock `StartUpdateAsync<TResult>()` + `GetResultAsync()` instead (see Pattern 1).

### ❌ Using expression-based QueryAsync in mock setup
```csharp
// THIS WILL FAIL — QueryAsync(Expression) is NOT virtual!
handleMock.Setup(x => x.QueryAsync(wf => wf.GetOrderStatus()))
    .ReturnsAsync(status);
```

✅ **Fix**: Use string-based `QueryAsync<TResult>("GetOrderStatus", ...)` (see Pattern 2).

### ❌ Using expression-based SignalAsync in mock setup
```csharp
// THIS WILL FAIL — SignalAsync(Expression) is NOT virtual!
handleMock.Setup(x => x.SignalAsync(wf => wf.UpdateInventory(qty)))
    .Returns(Task.CompletedTask);
```

✅ **Fix**: Use string-based `SignalAsync("UpdateInventory", ...)` (see Pattern 3).

### ❌ Forgetting GetResultAsync on update handle
```csharp
// Incomplete — will throw NullReferenceException or return default
var updateHandle = new Mock<WorkflowUpdateHandle<OrderResponse>>(...);
// Missing: .Setup(x => x.GetResultAsync(...))
```

✅ **Fix**: Always chain `GetResultAsync<TResult>()` setup on the update handle.

### ❌ Wrong generic type for GetResultAsync
```csharp
// Wrong — using workflow return type instead of update return type
updateHandle.Setup(x => x.GetResultAsync<WorkflowResult>(...))
    .ReturnsAsync(workflowResult);
```

✅ **Fix**: Match the update method's return type exactly. For void updates use `GetResultAsync<ValueTuple>()` returning `default(ValueTuple)`.

### ❌ Missing constructor parameters for mock handles
```csharp
// Will fail at runtime — missing required constructor parameters
var handle = new Mock<WorkflowHandle<IOrderWorkflow>>();
```

✅ **Fix**: Provide all constructor params: `new Mock<WorkflowHandle<IOrderWorkflow>>(clientMock.Object, "workflow-id", null, null, null)`.

---

## Activity Testing

### Simple Activity Tests (No Temporal Context)

Activities that don't use `ActivityExecutionContext` can be tested as plain classes:

```csharp
[Fact]
public async Task ProcessOrder_ReturnsResult()
{
    // Arrange
    var mockService = new Mock<IOrderService>();
    mockService.Setup(x => x.ProcessAsync(It.IsAny<OrderRequest>()))
        .ReturnsAsync(new OrderResult { Status = "OK" });

    var activity = new OrderActivities(mockService.Object);

    // Act
    var result = await activity.ProcessOrder(new OrderRequest { OrderId = "123" });

    // Assert
    Assert.Equal("OK", result.Status);
}
```

### Activity Tests with ActivityEnvironment

When activities use `ActivityExecutionContext.Current`, use `ActivityEnvironment` from `Temporalio.Testing`:

```csharp
[Fact]
public async Task Activity_WithHeartbeat_CompletesSuccessfully()
{
    // Arrange
    var env = new ActivityEnvironment();
    var activity = new LongRunningActivity(new Mock<IBlobService>().Object);

    // Act
    var result = await env.RunAsync(() => activity.ProcessLargeFile(new FileRequest()));

    // Assert
    Assert.NotNull(result);
}
```

---

## Test Setup Patterns

### Service with Keyed Services

Services use `[FromKeyedServices]` for named Temporal client injection:

```csharp
public class PaymentService
{
    private readonly ITemporalClient _paymentsClient;

    public PaymentService([FromKeyedServices("payments")] ITemporalClient paymentsClient)
    {
        _paymentsClient = paymentsClient ?? throw new ArgumentNullException(nameof(paymentsClient));
    }
}
```

Test initialization — inject mock directly (no DI container):

```csharp
public class PaymentServiceTests
{
    private readonly Mock<ITemporalClient> _paymentsClientMock = new();
    private readonly PaymentService _sut;

    public PaymentServiceTests()
    {
        _sut = new PaymentService(_paymentsClientMock.Object);
    }
}
```

### Controller with Multiple Keyed Clients

```csharp
public class FulfillmentController(
    IMapper mapper,
    IDateTimeProvider dateTimeProvider,
    [FromKeyedServices("fulfillment")] ITemporalClient fulfillmentClient,
    [FromKeyedServices("orders")] ITemporalClient ordersClient)
```

Test setup — use tuple for multiple mocks:

```csharp
private (FulfillmentController Controller,
         Mock<ITemporalClient> FulfillmentClientMock,
         Mock<ITemporalClient> OrdersClientMock) InitializeController()
{
    var fulfillmentClientMock = new Mock<ITemporalClient>();
    var ordersClientMock = new Mock<ITemporalClient>();

    var controller = new FulfillmentController(
        _mapper, _dateTimeProviderMock.Object,
        fulfillmentClientMock.Object, ordersClientMock.Object);

    return (controller, fulfillmentClientMock, ordersClientMock);
}
```

---

## Helper Utilities

### ExtractArgumentValues

`YourOrg.Temporal.Testing.ExtractArgumentValues` — extracts argument values from captured `MethodCallExpression` for assertion:

```csharp
// Capture expression in .Callback()
var capturedExpression = default(Expression<Func<IOrderWorkflow, Task>>);
clientMock.Setup(m => m.StartUpdateWithStartWorkflowAsync(
        It.IsAny<Expression<Func<IOrderWorkflow, Task>>>(),
        It.IsAny<WorkflowStartUpdateWithStartOptions>()))
    .Callback<Expression<Func<IOrderWorkflow, Task>>, WorkflowStartUpdateWithStartOptions>(
        (expr, opts) => capturedExpression = expr)
    .ReturnsAsync(handle.Object);

// After Act — extract and validate
var methodCall = (MethodCallExpression)capturedExpression!.Body;
Assert.Equal("PlacedOrderUpdate", methodCall.Method.Name);

var arguments = ExtractArgumentValues.From(methodCall);
Assert.Equal(expectedInput, arguments[0]);
```

### AsyncEnumerable Helpers

For mocking `ListWorkflowsAsync`:

```csharp
using System.Linq; // For .ToAsyncEnumerable()

// Empty result (no workflows found)
clientMock.Setup(x => x.ListWorkflowsAsync(query, null))
    .Returns(AsyncEnumerable.Empty<WorkflowExecution>());

// With results (workflows found)
var workflows = new[] { workflowInfo1, workflowInfo2 };
clientMock.Setup(x => x.ListWorkflowsAsync(query, null))
    .Returns(workflows.ToAsyncEnumerable());
```

---

## Integration Testing

### Choosing a Test Server: Time-Skipping vs Local

> **⚠️ CRITICAL: `StartTimeSkippingAsync()` does NOT support Nexus operations.**
>
> The time-skipping test server is a Java-based process that lacks Nexus support ([temporalio/sdk-dotnet#578](https://github.com/temporalio/sdk-dotnet/issues/578)). If a workflow calls a Nexus operation in a time-skipping environment, the Nexus task is silently dropped — the workflow hangs indefinitely with no error, no timeout, no log output. This is extremely difficult to diagnose.
>
> **Use `StartLocalAsync()`** for any test where the workflow invokes Nexus operations.

| Environment | Method | Timer Behavior | Nexus Support | Use When |
|-------------|--------|----------------|---------------|----------|
| **Time-skipping** | `StartTimeSkippingAsync()` | Instant — timers skip to completion | ❌ **No** | Non-Nexus workflow tests, especially those with long timers (hours/days) |
| **Local** | `StartLocalAsync()` | Real-time — timers run at wall-clock speed | ✅ **Yes** | Nexus workflow tests, replay tests, search attribute tests |

**Design implication**: If a workflow uses both Nexus operations and long timers, you need **two test classes** — one per server type. Tests that don't touch Nexus can use time-skipping for speed; tests that exercise Nexus paths must use local. See `a production codebase` for a real example (`OrderWorkflowTimeSkippingTests` + `OrderWorkflowLocalTests`).

**Local environment timer workaround**: Since `StartLocalAsync()` can't skip time, keep timer durations short in test data. If the workflow reads durations from configuration/input (e.g., `ExecutionOptions.ValidationDeadline`), set them to seconds in test fixtures rather than the production values (hours/days).

### WorkflowEnvironment Setup

```csharp
// ✅ For non-Nexus tests — timers skip instantly
public class OrderWorkflowTimeSkippingTests : IAsyncLifetime
{
    private WorkflowEnvironment _env = null!;

    public async Task InitializeAsync()
    {
        _env = await WorkflowEnvironment.StartTimeSkippingAsync();
    }

    public async Task DisposeAsync()
    {
        await _env.ShutdownAsync();
    }
}

// ✅ For Nexus tests — full server, real-time timers
public class OrderWorkflowLocalTests : IAsyncLifetime
{
    private WorkflowEnvironment _env = null!;

    public async Task InitializeAsync()
    {
        _env = await WorkflowEnvironment.StartLocalAsync();
    }

    public async Task DisposeAsync()
    {
        await _env.ShutdownAsync();
    }
}
```

### BaseWorkflowEnvironment Pattern

Create a reusable base class for workflow tests:

```csharp
public class BaseWorkflowEnvironment(ITestOutputHelper? output = null)
    : BaseUnitTest
{
    public Mock<ILogger>? LoggerMock;
    public WorkflowEnvironment? WorkflowEnvironment;
    public TemporalClient? Client;
    public TemporalWorker? TemporalWorker;

    protected override object[] ExcludedMocksFromVerification => [LoggerMock!];

    /// <summary>
    /// Assertion helper — retries until assertion passes.
    /// </summary>
    protected static async Task<T> AssertEventuallyAsync<T>(
        Func<Task<T>> func, TimeSpan? interval = null, int iterations = 15)
    {
        var tick = interval ?? TimeSpan.FromMilliseconds(300);
        for (var i = 0; ; i++)
        {
            try { return await func(); }
            catch (Xunit.Sdk.XunitException) { if (i >= iterations - 1) throw; }
            await Task.Delay(tick);
        }
    }

    protected TemporalWorkerOptions CreateTemporalWorkerOptions() => new()
    {
        DebugMode = true,
        TaskQueue = "test",
        WorkflowStackTrace = WorkflowStackTrace.Normal,
        LoggerFactory = TemporalLoggerFactoryEnvironment(LoggerMock),
    };

    protected static WorkflowOptions CreateWorkflowOptions(string id, string taskQueue) => new()
    {
        Id = id,
        TaskQueue = taskQueue,
        IdConflictPolicy = WorkflowIdConflictPolicy.UseExisting,
        IdReusePolicy = WorkflowIdReusePolicy.AllowDuplicateFailedOnly,
        RetryPolicy = new RetryPolicy { MaximumAttempts = 1 },  // Fail fast in tests
    };

    protected ILoggerFactory TemporalLoggerFactoryEnvironment(Mock<ILogger>? loggerMock)
    {
        return LoggerFactory.Create(configure =>
        {
            if (output != null) configure.AddXUnit(output);
            configure.SetMinimumLevel(LogLevel.Information);
            loggerMock ??= new Mock<ILogger>();
            var loggerProvider = new Mock<ILoggerProvider>();
            loggerProvider.Setup(x => x.CreateLogger(It.IsAny<string>()))
                .Returns(loggerMock.Object);
            configure.AddProvider(loggerProvider.Object);
        });
    }
}
```

### Full Workflow Integration Test

```csharp
[Fact]
public async Task OrderWorkflow_EndToEnd_ProcessesOrder()
{
    // Arrange
    var workerOptions = CreateTemporalWorkerOptions()
        .AddWorkflow<OrderWorkflow>()
        .AddActivity(_validateMock.Object.MassageStagedOrderActivity)
        .AddActivity(_validateMock.Object.ValidateProductsActivityAsync);
    TemporalWorker = new TemporalWorker(WorkflowEnvironment.Client, workerOptions);

    // Act & Assert
    var actual = await TemporalWorker.ExecuteAsync(async () =>
    {
        var wfInput = _orderEntityRequest.Clone();
        var wfOptions = CreateWorkflowOptions(wfInput.PlacedOrder.OrderId,
            TemporalWorker.Options.TaskQueue);
        var wfOperation = WithStartWorkflowOperation.Create<IOrderWorkflow>(
            wf => wf.RunAsync(wfInput), wfOptions);

        var updateInput = _fulfillmentOrderUpdateInput.Clone();
        updateInput.WaitForAction = FulfillmentAction.Validation;

        _ = Client.ExecuteUpdateWithStartWorkflowAsync<IOrderWorkflow,
            FulfillmentOrderUpdateResponse?>(
            act => act.FulfillmentOrderUpdate(updateInput),
            new(wfOperation));

        var handle = await wfOperation.GetHandleAsync();
        return await handle.QueryAsync(wf => wf.GetOrderEntityState(null));
    }, _cancellationToken);

    Assert.NotNull(actual);
    VerifyMocks();
}
```

### Workflow Test Init/Dispose Pattern

```csharp
public class OrderWorkflowTests(ITestOutputHelper output)
    : BaseWorkflowEnvironment(output), IAsyncLifetime
{
    private readonly CancellationToken _cancellationToken = TestContext.Current.CancellationToken;

    public async ValueTask InitializeAsync()
    {
        LoggerMock = new Mock<ILogger>();
        WorkflowEnvironment = await WorkflowEnvironment.StartTimeSkippingAsync();
        WorkflowEnvironment.Client.Options.LoggerFactory =
            TemporalLoggerFactoryEnvironment(LoggerMock);
        Client = new TemporalClient(
            WorkflowEnvironment.Client.Connection,
            WorkflowEnvironment.Client.Options);
    }

    public async ValueTask DisposeAsync()
    {
        GC.SuppressFinalize(this);
        TemporalWorker?.Dispose();
        await WorkflowEnvironment?.ShutdownAsync();
        await WorkflowEnvironment?.DisposeAsync().AsTask();
    }
}
```
```

### Nexus Integration Test

```csharp
[Fact]
public async Task NexusOperation_EndToEnd()
{
    var handlerTQ = $"handler-{Guid.NewGuid()}";
    var callerTQ = $"caller-{Guid.NewGuid()}";

    // Create Nexus endpoint pointing to handler task queue
    await _env.CreateNexusEndpointAsync("order-endpoint", handlerTQ);

    // Start handler worker (Nexus service + backing workflows)
    using var handlerWorker = new TemporalWorker(_env.Client,
        new TemporalWorkerOptions(handlerTQ)
            .AddNexusService(new OrderNexusService())
            .AddWorkflow<OrderHandlerWorkflow>());

    await handlerWorker.ExecuteAsync(async () =>
    {
        // Start caller worker
        using var callerWorker = new TemporalWorker(_env.Client,
            new TemporalWorkerOptions(callerTQ)
                .AddWorkflow<CallerWorkflow>());

        await callerWorker.ExecuteAsync(async () =>
        {
            var result = await _env.Client.ExecuteWorkflowAsync(
                (CallerWorkflow wf) => wf.RunAsync(new CallerInput()),
                new(id: $"caller-{Guid.NewGuid()}", taskQueue: callerTQ));

            Assert.NotNull(result);
        });
    });
}
```

### Time-Skipping for Timers

```csharp
[Fact]
public async Task Workflow_WithTimer_SkipsTime()
{
    var taskQueue = $"tq-{Guid.NewGuid()}";

    using var worker = new TemporalWorker(_env.Client,
        new TemporalWorkerOptions(taskQueue)
            .AddWorkflow<ReminderWorkflow>());

    await worker.ExecuteAsync(async () =>
    {
        // Time-skipping environment automatically advances time
        // when workflow calls Workflow.DelayAsync()
        var result = await _env.Client.ExecuteWorkflowAsync(
            (ReminderWorkflow wf) => wf.RunAsync(new ReminderInput { Delay = TimeSpan.FromHours(24) }),
            new(id: $"wf-{Guid.NewGuid()}", taskQueue: taskQueue));

        Assert.True(result.ReminderSent);
    });
}
```

### Workflow Replay Testing

Replay tests verify that changes to workflow code don't break compatibility with previously executed workflows. **Critical for backward compatibility.** Run these as build validation tests — ideally before other unit/functional tests.

**Replay Test Recommendations** (from [Temporal Jumpstart Foundations](https://github.com/temporalio/temporal-jumpstart/blob/main/docs/foundations/Versions.md)):
- **Scope**: Make each Workflow the boundary for a Replay test
- **Dependencies**: Provide Activity or ChildWorkflow doubles to test various conditional paths
- **Scenarios**: Reproduce the scenarios from your functional/unit tests to produce various histories for replay validation
- **Deployments**: Rolling deployments create races — code defensively against service message contract evolution
- **Schema changes**: Always verify with Replay tests when changing message schemas that appear in workflow history

```csharp
public class OrderWorkflowReplayTests(ITestOutputHelper output)
    : BaseWorkflowEnvironment(output), IAsyncLifetime
{
    public async ValueTask InitializeAsync()
    {
        // Use StartLocalAsync with search attributes for replay tests
        WorkflowEnvironment = await WorkflowEnvironment.StartLocalAsync(new()
        {
            SearchAttributes =
            [
                SearchAttributeKey.CreateKeyword("OrderId"),
                SearchAttributeKey.CreateKeyword("ExternalOrderId"),
            ],
        });
        Client = new TemporalClient(
            WorkflowEnvironment.Client.Connection,
            WorkflowEnvironment.Client.Options);
    }

    [Fact]
    public async Task RunAsync_ShouldReplayOK_WhenGivenSameType()
    {
        // Arrange — run workflow to completion, capturing history
        var workerOptions = CreateTemporalWorkerOptions()
            .AddWorkflow<OrderWorkflow>()
            .AddActivity(_validateMock.Object.MassageStagedOrderActivity)
            .AddActivity(_validateMock.Object.ValidateProductsActivityAsync)
            .AddNexusService(new FakeNexusServiceHandler());

        TemporalWorker = new TemporalWorker(WorkflowEnvironment.Client, workerOptions);
        await WorkflowEnvironment.CreateNexusEndpointAsync(
            "ofo-nexus-test", workerOptions.TaskQueue);

        WorkflowHistory? history = null;
        await TemporalWorker.ExecuteAsync(async () =>
        {
            // ... execute workflow to completion ...
            var handle = await wfOperation.GetHandleAsync();
            await AssertEventuallyAsync(async () =>
            {
                history = await handle.FetchHistoryAsync();
            });
        }, _cancellationToken);

        // Act — replay with current code
        var replayer = new WorkflowReplayer(
            new WorkflowReplayerOptions { DebugMode = true }
                .AddWorkflow<OrderWorkflow>());

        // Assert
        Assert.NotNull(history);
        var result = await replayer.ReplayWorkflowAsync(history, false);
        Assert.Null(result.ReplayFailure);
    }
}
```

### Activity Stub Naming — Explicit `[Activity("Name")]` Required

> **⚠️ CRITICAL:** When an activity interface uses an explicit name in `[Activity("ExplicitName")]`, test stubs **MUST** use the same explicit name. Using bare `[Activity]` auto-generates the name from the method name, causing a **silent mismatch** — the workflow hangs indefinitely waiting for an activity that's registered under a different name.

```csharp
// ❌ WRONG — interface says [Activity("OccGetCartActivity")] on method GetCart
//           but bare [Activity] auto-names this "GetCart" → workflow can't find it → HANGS
[Activity]
public Task<Response> GetCart(Request request) => Task.FromResult(new Response());

// ✅ CORRECT — explicit name matches the interface's [Activity("OccGetCartActivity")]
[Activity("OccGetCartActivity")]
public Task<Response> GetCart(Request request) => Task.FromResult(new Response());
```

**Rule:** Always check the activity interface's `[Activity]` attribute. If it specifies an explicit name different from the method name, your test stub must use that same explicit name.

**When is bare `[Activity]` OK?** Only when the interface either uses bare `[Activity]` too, or uses `[Activity("SameName")]` where `"SameName"` matches your stub's method name exactly.

### Local Activity Retry Behavior Tests

> **⚠️** These tests prove that local activities with default retry policy silently swallow exceptions. See SKILL.md § "Local Activity Gotchas" for the full explanation.

**Two key behaviors to verify:**

1. **Default policy (no `MaximumAttempts`)** — failures are silently retried; the workflow caller never sees the exception
2. **`MaximumAttempts = 1`** — the exception surfaces immediately as `ApplicationFailureException`

**Test design considerations:**
- Do NOT rely on `ScheduleToCloseTimeout` to bound retry tests — local activity retry backoff runs on worker wall-clock time, which the time-skipping test server cannot accelerate. Tests will hang.
- Instead, use a **counting activity** that fails N times then succeeds — this bounds the test without timeout dependency.
- Always use class-based `ExecuteLocalActivityAsync<TActivityType, TResult>(act => act.Method(), ...)` — delegate-based `(Func<T, R> act) => act(input)` resolves to `Func.Invoke` and the SDK cannot match it to registered activities, causing the workflow to hang indefinitely.
- Set `DebugMode = true` on `TemporalWorkerOptions` to get better diagnostic output.
- Set workflow-level `RetryPolicy { MaximumAttempts = 1 }` to prevent the workflow itself from retrying on failure.

```csharp
public class LocalActivityRetryBehaviorTests : IAsyncLifetime
{
    private WorkflowEnvironment _env = null!;
    private ITemporalClient _client = null!;

    public async Task InitializeAsync()
    {
        _env = await WorkflowEnvironment.StartTimeSkippingAsync();
        _client = _env.Client;
    }

    public async Task DisposeAsync()
    {
        await _env.ShutdownAsync();
        await _env.DisposeAsync();
    }

    /// Default policy: activity fails 2x, succeeds 3rd — proves silent retries
    [Fact]
    public async Task LocalActivity_DefaultRetryPolicy_RetriesSilently()
    {
        var activities = new CountingActivity(maxFailures: 2);
        using var worker = new TemporalWorker(_client,
            new TemporalWorkerOptions("default-retry-queue") { DebugMode = true }
                .AddWorkflow<DefaultRetryWorkflow>()
                .AddAllActivities(activities));

        var result = await worker.ExecuteAsync(async () =>
            await _client.ExecuteWorkflowAsync(
                (DefaultRetryWorkflow wf) => wf.RunAsync("bad-value"),
                new WorkflowOptions
                {
                    Id = $"default-retry-{Guid.NewGuid():N}",
                    TaskQueue = "default-retry-queue",
                    RetryPolicy = new RetryPolicy { MaximumAttempts = 1 }
                }));

        Assert.Equal(3, activities.CallCount);  // 2 failures silently retried + 1 success
        Assert.Equal("success-bad-value", result);
    }

    /// MaximumAttempts=1: exception surfaces immediately
    [Fact]
    public async Task LocalActivity_MaximumAttempts1_SurfacesExceptionImmediately()
    {
        var activities = new CountingActivity();  // always fails
        using var worker = new TemporalWorker(_client,
            new TemporalWorkerOptions("noretry-queue") { DebugMode = true }
                .AddWorkflow<NoRetryWorkflow>()
                .AddAllActivities(activities));

        var ex = await worker.ExecuteAsync(async () =>
            await Assert.ThrowsAsync<WorkflowFailedException>(() =>
                _client.ExecuteWorkflowAsync(
                    (NoRetryWorkflow wf) => wf.RunAsync("bad-value"),
                    new WorkflowOptions
                    {
                        Id = $"noretry-{Guid.NewGuid():N}",
                        TaskQueue = "noretry-queue",
                        RetryPolicy = new RetryPolicy { MaximumAttempts = 1 }
                    })));

        Assert.Equal(1, activities.CallCount);
        var appFailure = Assert.IsType<ApplicationFailureException>(ex.InnerException);
        Assert.Contains("NotSupportedException", appFailure.ErrorType);
        Assert.Contains("Unmapped value: bad-value", appFailure.Message);
    }

    // --- Supporting types ---

    public class CountingActivity(int maxFailures = int.MaxValue)
    {
        private int _callCount;
        public int CallCount => _callCount;

        [Activity]
        public string Execute(string input)
        {
            var count = Interlocked.Increment(ref _callCount);
            if (count <= maxFailures)
                throw new NotSupportedException($"Unmapped value: {input}");
            return $"success-{input}";
        }
    }

    [Workflow]
    public class DefaultRetryWorkflow
    {
        [WorkflowRun]
        public async Task<string> RunAsync(string input) =>
            await Workflow.ExecuteLocalActivityAsync<CountingActivity, string>(
                act => act.Execute(input),
                new LocalActivityOptions { StartToCloseTimeout = TimeSpan.FromSeconds(10) });
                // No RetryPolicy → unlimited retries (default)
    }

    [Workflow]
    public class NoRetryWorkflow
    {
        [WorkflowRun]
        public async Task<string> RunAsync(string input) =>
            await Workflow.ExecuteLocalActivityAsync<CountingActivity, string>(
                act => act.Execute(input),
                new LocalActivityOptions
                {
                    StartToCloseTimeout = TimeSpan.FromSeconds(10),
                    RetryPolicy = new RetryPolicy { MaximumAttempts = 1 }
                });
    }
}
```

**Key observations from these tests:**
- With default policy, 2 `NotSupportedException`s were thrown and **completely invisible** to the workflow caller — the workflow succeeded
- With `MaximumAttempts = 1`, the exception surfaces as `WorkflowFailedException` → `ApplicationFailureException` (not wrapped in `ActivityFailureException` for local activities)
- The `ErrorType` for local activity failures may not include the full namespace (e.g., `"NotSupportedException"` not `"System.NotSupportedException"`) — use `Assert.Contains` instead of `Assert.Equal`

### Fake Nexus Service Handlers for Testing

Create fake handlers for Nexus services that the workflow calls:

```csharp
[NexusServiceHandler(typeof(IPaymentProcessNexusService))]
private class FakeNexusServiceHandler
{
    [NexusOperationHandler]
    public IOperationHandler<FinalizeOrderRequest, FinalizeOrderResponse> FinalizeOrder() =>
        OperationHandler.Sync<FinalizeOrderRequest, FinalizeOrderResponse>(HandleFinalizeOrder);

    private Task<FinalizeOrderResponse> HandleFinalizeOrder(
        OperationStartContext context, FinalizeOrderRequest request)
    {
        return Task.FromResult(new FinalizeOrderResponse
        {
            PaymentProcessedDetails = new PaymentProcessed
            {
                OrderId = request.OrderId,
                Decision = "approved",
            }
        });
    }
}
```

Register fake handlers in worker options:
```csharp
var workerOptions = CreateTemporalWorkerOptions()
    .AddWorkflow<OrderWorkflow>()
    .AddNexusService(new FakeNexusServiceHandler());
await WorkflowEnvironment.CreateNexusEndpointAsync("my-endpoint", workerOptions.TaskQueue);
```

---

## Test Decision Matrix

| Scenario | Unit Test | Integration Test |
|----------|-----------|------------------|
| Activity business logic | ✅ Mock dependencies | ✅ With real services |
| Workflow query/signal/update callers | ✅ Mock `WorkflowHandle<T>` | ✅ Full workflow |
| Nexus handler logic | ✅ Three-method pattern (Spy class) | ✅ With `CreateNexusEndpointAsync` |
| Update-with-start | ✅ `.Callback()` + expression capture | ✅ Recommended |
| Exception-then-query fallback | ✅ Chain update throw + query mock | ✅ Full workflow |
| Timer/delay behavior | ❌ | ✅ Time-skipping env |
| Workflow orchestration | ❌ | ✅ Required |
| Error/retry behavior | ❌ | ✅ Required |
| Local activity retry masking | ❌ | ✅ Counting activity pattern |
| Cross-namespace Nexus calls | ❌ | ✅ `StartLocalAsync` + Fake Nexus handler + endpoint (**not** time-skipping — hangs silently) |
| Workflow backward compatibility | ❌ | ✅ Replay tests (`WorkflowReplayer`) |

---

## Verification Checklist

Before claiming tests are complete:

**Mocking correctness:**
- [ ] All update mocks use `StartUpdateAsync` (string-based) + `GetResultAsync`
- [ ] All query mocks use string-based `QueryAsync<T>("MethodName", args, options)`
- [ ] All signal mocks use string-based `SignalAsync("MethodName", args, options)`
- [ ] `WorkflowHandle<T>` mocks have 5 constructor params (client, id, runId, firstExecutionRunId, resultRunId)
- [ ] `WorkflowUpdateHandle<T>` mocks have 4 constructor params (client, updateId, workflowId, workflowRunId)
- [ ] `GetResultAsync` generic type matches update method return type
- [ ] Void updates use `GetResultAsync<ValueTuple>()` returning `default(ValueTuple)`
- [ ] `MockBehavior.Strict` used for `ITemporalClient` mocks in Nexus tests
- [ ] No mocking of `NexusOperationExecutionContext.Current`

**Method name correctness:**
- [ ] String method names match exact workflow interface method names
- [ ] Activity stubs use explicit `[Activity("Name")]` matching the interface
- [ ] Local activities have `RetryPolicy { MaximumAttempts = 1 }` unless retry is intentional
- [ ] Local activity tests use class-based `ExecuteLocalActivityAsync<TActivity, TResult>(act => act.Method(...))`, not `Func<>` delegates
- [ ] No expression-based calls used in mock setups
- [ ] Update-with-start uses `.Callback()` to capture + validate expression

**Keyed services:**
- [ ] Services use `[FromKeyedServices("key")]` attribute for DI
- [ ] Each keyed service has separate mock instance
- [ ] Test constructor directly injects mocks (no DI container)

**Nexus testing:**
- [ ] Nexus handlers use three-method testability pattern with Spy class
- [ ] Nexus handler private methods marked `[ExcludeFromCodeCoverage]`
- [ ] Fake Nexus service handlers created for cross-namespace calls

**Exception handling:**
- [ ] Exception scenarios test appropriate `RpcException` status codes
- [ ] Exception-then-query fallback patterns tested (update throws → query called)
- [ ] Non-testable scenarios marked with `[Fact(Skip="...")]` with explanation

**Integration & replay:**
- [ ] Integration tests use unique task queues (`$"tq-{Guid.NewGuid()}"`)
- [ ] Integration tests properly dispose `WorkflowEnvironment`
- [ ] Replay tests exist for workflows with production traffic
- [ ] Replay tests cover various conditional paths via Activity/ChildWorkflow doubles

**Environment selection:**
- [ ] Tests with Nexus operations use `StartLocalAsync()` — never `StartTimeSkippingAsync()` (hangs silently)
- [ ] Tests with long timers and no Nexus use `StartTimeSkippingAsync()` for speed
- [ ] If workflow has both Nexus and timers, tests are split across two classes

**Foundations alignment:**
- [ ] Workflow state verified via Query, not just return value (avoids coupling callers to result contract)
- [ ] Both success and failure scenarios tested
- [ ] Failed workflows verified as still queryable for state
- [ ] Test isolation boundary explicitly chosen (mock Activities vs mock their dependencies)
- [ ] Configurable durations used in integration tests (ExecutionOptions) for fast execution
- [ ] Test names follow pattern: `MethodName_Condition_ExpectedOutcome`
