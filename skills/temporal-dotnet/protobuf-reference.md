# Protobuf & Project Structure Reference — Temporal .NET

Temporal-specific protobuf patterns, project layout, and constants. Supplements the main SKILL.md.

> **For general protobuf guidance** — schema design rules, buf configuration, .csproj integration, code generation workflow, schema evolution, and extension method patterns — see the `protobuf-dotnet` skill.

---

## Contents

- [Temporal Schema Organization](#temporal-schema-organization)
- [Project Structure](#project-structure)
- [Constants & Naming Patterns](#constants--naming-patterns)

---

## Temporal Schema Organization

Organize messages within `workflows.proto` using comment section markers. This convention groups related Temporal contract messages:

```protobuf
// WorkflowRun
message OrderEntityRequest { /* ... */ }
// end WorkflowRun

// WorkflowQuery
message GetOrderEntityStateRequest {}
message GetOrderEntityStateResponse { /* ... */ }
// end WorkflowQuery

// WorkflowUpdate
message FulfillmentOrderUpdateRequest { /* ... */ }
message FulfillmentOrderUpdateResponse { /* ... */ }
// end WorkflowUpdate

// Nexus Operation
message UpdatePlacedOrderNexusRequest { /* ... */ }
message UpdatePlacedOrderNexusResponse {}
// end Nexus Operation

// Activity
message ValidateProductsActivityRequest { /* ... */ }
message ValidateProductsActivityResponse { /* ... */ }
// end Activity

// Execution Options
message OrderEntityExecutionOptions { /* ... */ }
// end Execution Options
```

### Using Generated Types in Temporal Interfaces

```csharp
[Workflow]
public interface IOrderWorkflow
{
    [WorkflowRun]
    Task<FulfillmentStatus> RunAsync(OrderRequest request);

    [WorkflowUpdate]
    Task<FulfillmentUpdateResponse> FulfillmentUpdate(FulfillmentUpdateRequest request);

    [WorkflowQuery]
    Task<GetOrderStateResponse> GetOrderState(GetOrderStateRequest request);
}
```

**Key Temporal schema rules:**
- **Single message per operation** — Temporal SDK expects one parameter object per workflow/activity method
- **Request/response pairs** — all updates and queries must have matching request/response messages
- Schema evolution impacts running workflow event history — use **Replay tests** to verify compatibility

---

## Project Structure

```
proto/
└── your.namespace/          # Protobuf definitions
    └── domain/v1/
        ├── workflows.proto      # Run, update, query, activity messages
        └── values.proto         # Shared enums, value objects

src/
├── YourApp.Core/                    # Contracts, interfaces, generated protobuf
│   ├── Constants/                   # WorkflowId constants
│   ├── Extensions/                  # Extension methods for generated types
│   ├── Generated/                   # buf generate output (never edit)
│   ├── NexusContracts/              # [NexusService] interfaces
│   └── Workflows/                   # [Workflow] interfaces (IOrderWorkflow)
├── YourApp.Domain/                  # Domain constants, settings, models
│   ├── Constants/
│   │   ├── SectionName.cs           # Config section identifiers
│   │   └── Temporal/
│   │       ├── TaskQueueId.cs       # Task queue constants
│   │       └── BuildId.cs           # Worker build ID constants
│   └── Settings/                    # App-specific settings classes
├── YourApp.Application/             # Workflow + activity implementations
│   ├── Workflows/
│   │   ├── IOrderWorkflow.cs
│   │   ├── OrderWorkflow.workflow.cs
│   │   └── Utilities/               # Workflow helper classes
│   ├── Activities/
│   └── NexusServices/
├── YourApp.Infrastructure/          # Data/API/message adapters
├── YourApp.Workers/                 # Worker host (Program.cs)
├── YourApp.Api/                     # HTTP API / workflow starters
├── YourApp.AppHost/                 # Aspire orchestration
└── YourApp.ServiceDefaults/         # Shared service configuration

tests/
├── YourApp.Application.UnitTests/   # Workflow + activity + nexus tests
│   ├── Workflows/
│   ├── Activities/
│   ├── NexusServices/
│   ├── UnitTestsHelpers/            # BaseWorkflowEnvironment, test addons
│   └── TestData/                    # JSON test data files
├── YourApp.Api.UnitTests/           # API controller tests
├── YourApp.Domain.UnitTests/        # Domain logic tests
└── YourApp.IntegrationTests/        # WorkflowEnvironment, real Temporal
```

---

## Constants & Naming Patterns

### TaskQueueId and BuildId Constants

Use dedicated constants classes for Temporal identifiers:

```csharp
// Domain/Constants/Temporal/TaskQueueId.cs
public static class TaskQueueId
{
    public const string OrderFulfillmentCoordinator = "order-fulfillment-coordinator";
}

// Domain/Constants/Temporal/BuildId.cs
public static class BuildId
{
    public static string V1_0_0 => "1.0.0";
}

// Domain/Constants/SectionName.cs
public static class SectionName
{
    public const string Shared = "shared";
    public const string OrderFinalizationWorker = "order-finalization-worker";
    public const string FulfillmentWorker = "FulfillmentWorker";
    public const string FulfillmentClient = "FulfillmentClient";
}
```

### NamingRules Pattern

Use a static helper class for consistent workflow ID generation:

```csharp
// Core/NamingRules.cs
public static class NamingRules
{
    public static string GetOrderWorkflowId(string orderId) =>
        $"order-{orderId}";

    // Idempotent prefix helper
    public static string TryAndPrefixOrderWorkflowId(string identifier) =>
        identifier.StartsWith($"{WorkflowId.OrderWorkflowIdPrefix}-", StringComparison.OrdinalIgnoreCase)
            ? identifier
            : $"{WorkflowId.OrderWorkflowIdPrefix}-{identifier}";
}

// Core/Constants/WorkflowId.cs
public static class WorkflowId
{
    public const string OrderWorkflowIdPrefix = "order";
}
```
