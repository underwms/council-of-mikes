# Configuration Reference — Temporal .NET

Detailed reference for Temporal client/worker configuration, official SDK or wrapper-library registration patterns, and utilities. Supplements the main SKILL.md.

> **Tip**: For configuration questions not covered here, use the `mcp_temporal-docs_search_temporal_knowledge_sources` tool (if available) to search official Temporal documentation.

---

## Contents

- [TemporalSettings Properties](#temporalsettings-properties)
- [appsettings.json Structure](#appsettingsjson-structure)
- [Client Registration](#client-registration)
- [Worker Registration](#worker-registration)
- [Observability](#observability)
- [Testing Utilities](#testing-utilities)

---

## TemporalSettings Properties

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `ClientTargetHost` | `string?` | `"localhost:7233"` | Temporal server address |
| `ClientNamespace` | `string?` | `"default"` | Temporal namespace |
| `ApiKey` | `string?` | `null` | API key (auto-enables TLS when set) |
| `IsEnabled` | `bool` | `true` | Feature flag for Temporal |

---

## appsettings.json Structure

A common approach is **hierarchical binding**: a `shared` section provides defaults, and an app section provides overrides.

```json
{
  "shared": {
    "TemporalSettings": {
      "ClientTargetHost": "localhost:7233",
      "ClientNamespace": "default"
    }
  },
  "MyApp": {
    "TemporalSettings": {
      "ApiKey": "your-temporal-cloud-api-key"
    }
  }
}
```

### Multi-Client Config

```json
{
  "shared": {
    "TemporalSettings": {
      "PrimaryClient": {
        "ClientTargetHost": "primary.temporal.local:7233",
        "ClientNamespace": "primary-namespace"
      },
      "SecondaryClient": {
        "ClientTargetHost": "secondary.temporal.local:7233",
        "ClientNamespace": "secondary-namespace"
      }
    }
  },
  "MyApp": {
    "TemporalSettings": {
      "PrimaryClient": { "ApiKey": "primary-key" },
      "SecondaryClient": { "ApiKey": "secondary-key" }
    }
  }
}
```

### Cloud Config

When `ApiKey` is set, TLS is automatically enabled (`new TlsOptions()`). No mTLS certificate configuration needed — API key auth replaces it (mTLS was removed in v0.2.1).

### Local Development

```powershell
# Start Temporal dev server
temporal server start-dev

# Create additional namespaces (for multi-client)
temporal operator namespace create --namespace primary-namespace
temporal operator namespace create --namespace secondary-namespace
```

---

## Client Registration

### Single Client (Most Common)

Use the official SDK directly, or a wrapper helper such as `AddTemporalClient` — register `ITemporalClient` as a singleton.

```csharp
// From app section name
builder.AddTemporalClient("MyApp");

// Or with pre-bound settings
var settings = builder.BindTemporalSettings("MyApp");
builder.AddTemporalClient(settings);

// Or with app + client subsection (named config)
builder.AddTemporalClient("MyApp", "PrimaryClient");
```

**What it does automatically:**
- Uses SDK's `AddTemporalClient()` with lazy creation + eager connection validation
- Applies `CamelCasePayloadConverter` for camelCase JSON payloads
- Adds `TracingInterceptor` for OpenTelemetry
- Configures TLS + API key when `ApiKey` is set
- Wires `ILoggerFactory` from DI automatically
- Returns `bool IsEnabled` from settings

### Keyed Services for Multiple Clients

Use a helper such as `AddKeyedTemporalClient` when you need multiple named Temporal clients.

```csharp
// Registration — with pre-bound settings (preferred)
var fulfillmentSettings = builder.BindTemporalSettings("MyApp", "FulfillmentClient");
builder.AddKeyedTemporalClient(fulfillmentSettings, serviceKey: "fulfillment");

var ordersSettings = builder.BindTemporalSettings("MyApp", "OrdersClient");
builder.AddKeyedTemporalClient(ordersSettings, serviceKey: "orders");

// Or from section names (3-param)
builder.AddKeyedTemporalClient("MyApp", "PrimaryClient", serviceKey: "primary");

// Injection — use [FromKeyedServices] attribute
public class OrderService(
    [FromKeyedServices("fulfillment")] ITemporalClient fulfillmentClient,
    [FromKeyedServices("orders")] ITemporalClient ordersClient)
{ }
```

> **Note**: A helper like `AddKeyedTemporalClient` can use `TemporalClient.ConnectAsync()` directly when your DI setup needs multiple named clients and the SDK abstractions do not cover that scenario cleanly.

### Settings Binding (Hierarchical Config)

```csharp
// Binds shared + app-specific sections (app overrides shared)
var settings = builder.BindTemporalSettings("MyApp");
// → shared:TemporalSettings + MyApp:TemporalSettings

// With client subsection for multi-client
var settings = builder.BindTemporalSettings("MyApp", "PrimaryClient");
// → shared:TemporalSettings:PrimaryClient + MyApp:TemporalSettings:PrimaryClient
```

---

## Worker Registration

### AddHostedTemporalWorker

If your codebase provides a hosted-worker helper such as `AddHostedTemporalWorker`, it can handle client options, TLS/API key, tracing interceptors, and debug mode automatically. Otherwise, wire these options up with the official SDK directly.

```csharp
// Simplest form — reads from appsettings.json
builder.AddHostedTemporalWorker(
    appSectionName: "MyApp",
    taskQueue: TaskQueueId.OrderFulfillmentCoordinator,
    buildId: BuildId.V1_0_0)
.ConfigureOptions(o =>
{
    o.AddNexusService(new OrderNexusService());  // Register Nexus services
})
.AddWorkflow<OrderWorkflow>()
.AddSingletonActivities<IValidateActivities>()     // Singleton by interface
.AddScopedActivities<ITriggerOaoActivities>();      // Scoped by interface
```

### Activity Registration Methods

| Method | Lifetime | When to Use |
|--------|----------|-------------|
| `.AddSingletonActivities<IInterface>()` | Singleton | Stateless activities, thread-safe services |
| `.AddScopedActivities<IInterface>()` | Scoped | Activities needing per-call scope (DB contexts, etc.) |
| `.AddAllActivities(assembly)` | Default | Bulk register all `[Activity]` methods in assembly |
| `.AddActivity(mock.Object.Method)` | N/A | Unit tests — register mock activity methods directly |

> **Important**: Register the DI service separately: `builder.Services.AddScoped<IValidateActivities, ValidatedActivities>();`

### Overloads

```csharp
// 1. From app section (most common)
builder.AddHostedTemporalWorker(appSectionName, taskQueue, buildId);

// 2. From app + client section (multi-client)
builder.AddHostedTemporalWorker(appSectionName, clientSectionName, taskQueue, buildId);

// 3. From pre-bound settings
builder.AddHostedTemporalWorker(settings, taskQueue, buildId);

// All overloads accept optional WorkerDeploymentOptions
builder.AddHostedTemporalWorker(appSectionName, taskQueue, buildId, 
    new WorkerDeploymentOptions { /* ... */ });
```

**What it does automatically:**
- Configures `TemporalClientConnectOptions` with namespace, host, TLS, API key
- Applies `CamelCasePayloadConverter` (camelCase JSON serialization)
- Adds `TracingInterceptor` for OpenTelemetry spans
- Sets `DebugMode = true` in Development environment (disables deadlock detector)
- Creates `WorkerDeploymentVersion(taskQueue, buildId)` for worker versioning

---

## Observability

A Temporal wrapper library can automatically configure OpenTelemetry tracing via `TracingInterceptor` on all clients and workers.

**Important**: Even if a wrapper library helps wire tracing, you should explicitly add and configure OpenTelemetry in your application startup.

**Emitted telemetry** (when OpenTelemetry is configured):
- **Traces**: Workflow and activity execution spans
- **Metrics**: 40+ Temporal SDK metrics (workflow/activity/worker/client)
- **Metric tags**: `namespace`, `task_queue`, `workflow_type`, `activity_type`, `operation`

---

## Testing Utilities

### ExtractArgumentValues (from your Temporal testing utilities)

Extracts argument values from `MethodCallExpression` — useful for verifying arguments passed to workflows/activities in tests.

```csharp
using YourOrg.Temporal.Testing;

// Extract args from an expression like: wf => wf.RunAsync(myInput)
var methodCall = (MethodCallExpression)((LambdaExpression)expression).Body;
var args = ExtractArgumentValues.From(methodCall);
// args[0] == myInput
```

### CamelCasePayloadConverter

Default converter enforcing camelCase JSON serialization. Auto-applied by `AddTemporalClient` and `AddHostedTemporalWorker` style helpers. If you need custom serialization, pass a `DataConverter` parameter to override.
