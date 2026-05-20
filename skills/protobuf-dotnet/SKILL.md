---
name: protobuf-dotnet
description: Use when setting up Protocol Buffers in a .NET project, defining protobuf schemas, configuring buf CLI for C# code generation, integrating proto files into .csproj, or creating extension methods for Google protobuf types like Money, Decimal, Value, and Struct
---

# Protocol Buffers in .NET

Standard patterns for defining Protocol Buffer schemas, generating C# models with Buf CLI, and integrating protobuf into .NET projects. All contracts use versioned protobuf messages for type-safe, backward-compatible serialization.

> **Using protobuf with Temporal?** The `temporal-dotnet` skill covers Temporal-specific schema organization (workflow/update/query message sections, comment markers) and constants/naming patterns (TaskQueueId, BuildId, NamingRules).

---

## Contents

- [Prerequisites](#prerequisites)
- [Directory Structure](#directory-structure)
- [Buf Configuration](#buf-configuration)
- [File Types](#file-types)
- [Schema Design Rules](#schema-design-rules)
- [Code Generation Workflow](#code-generation-workflow)
- [csproj Integration](#csproj-integration)
- [Generated Code Handling](#generated-code-handling)
- [Schema Evolution](#schema-evolution)
- [Creating a New Domain Context](#creating-a-new-domain-context)
- [Verification Checklist](#verification-checklist)
- [Common Mistakes](#common-mistakes)

---

## Prerequisites

- **Buf CLI** — installed and on PATH
- **proto3 syntax** — basic understanding
- **NuGet packages** in consuming project:

| Package | Purpose |
|---------|---------|
| `Google.Protobuf` | Runtime + well-known types (`Timestamp`, `Value`, `Struct`) |
| `Google.Api.CommonProtos` | Google domain types (`Money`, `Decimal`) |
| `Grpc` | gRPC service stubs (if using gRPC) |
| `Newtonsoft.Json` | Fallback JSON serializer for protobuf Value↔CLR conversions |

---

## Directory Structure

All protobuf schemas live in a top-level `proto/` directory with strict versioning:

```
proto/
└── {dotted.namespace}/
    └── domain/
        ├── {context-a}/
        │   └── v1/
        │       ├── workflows.proto   # Run, update, query, activity, nexus messages
        │       ├── values.proto      # Shared enums, value objects
        │       ├── commands.proto    # Command messages (placeholder if unused)
        │       └── queries.proto    # Standalone queries (placeholder if unused)
        └── {context-b}/
            └── v1/
                └── ...
```

**Key principles:**
- **Version directories** — always `/v1/`, `/v2/`, etc.
- **Domain separation** — group by bounded context (order, shadow, payment…)
- **File-per-concern** — workflows, values, commands, queries
- **Package = path** — `package dotted.namespace.domain.context.v1;` mirrors directory

---

## Buf Configuration

Copy the template files from this skill directory into your repository root:

| Template | Purpose | Placeholders |
|----------|---------|-------------|
| `buf.yaml.template` | Module config, lint rules, breaking change detection | `{YOUR_NAMESPACE}`, `{CONTEXT}` |
| `buf.gen.yaml.template` | C# code generation with remote plugins | `{YOUR_PROJECT}`, `{YOUR_NAMESPACE}` |

Rename to `buf.yaml` and `buf.gen.yaml` after replacing placeholders.

After adding deps, run `buf dep update` to generate/refresh `buf.lock`.

**Key `buf.gen.yaml` settings:**
- `managed: enabled: true` — applies Buf-managed mode (optimizes code generation)
- `remote` plugins — no local protoc installation required
- `base_namespace` — strips this prefix from generated namespace folders
- `out` — target directory for generated C# files

---

## File Types

| File | Contains | Use For |
|------|----------|---------|
| `workflows.proto` | Run input, update request/response, query request/response, activity request/response, nexus operation, execution options | Primary contract definitions |
| `values.proto` | Shared enums, domain value objects referenced across messages | Reusable types (FulfillmentType, LineItem…) |
| `commands.proto` | Command messages | Future use; keep as placeholder |
| `queries.proto` | Standalone query messages | When queries outgrow workflows.proto |

### Enum Pattern

```protobuf
enum FulfillmentType {
    FULFILLMENT_TYPE_UNSPECIFIED = 0;   // Always first, always 0
    FULFILLMENT_TYPE_PICKUP = 1;
    FULFILLMENT_TYPE_DELIVERY = 2;
    FULFILLMENT_TYPE_CURBSIDE = 3;
}
```

- First value **must** be `_UNSPECIFIED = 0` (buf lint enforces this)
- Prefix every value with the enum name in `UPPER_SNAKE_CASE`
- Use an `Errors` enum for `ApplicationFailureException` error types

### Cross-Domain Imports

Proto files can import from other domain contexts:

```protobuf
import "dotted.namespace/domain/order/v1/workflows.proto";

message ShadowWorkflowRequest {
  string workflow_suffix = 1;
  dotted.namespace.domain.order.v1.InflatableLineItem line_item = 2;
}
```

---

## Schema Design Rules

### 1. Single Message Per Request/Response

```protobuf
// ✅ Single wrapper message
message UpdateRequest {
    google.protobuf.Timestamp timestamp = 1;
    FulfillmentOrder order = 2;
    bool can_finalize = 3;
}

// ❌ Multiple parameters (not supported by Temporal SDK)
// rpc Process(Order, Timestamp, bool) returns (Status);
```

### 2. Version Everything

Schemas **must** live under `/v1/`, `/v2/`, etc. Never place protos at the domain root.

### 3. Package Matches Directory

```protobuf
// File: proto/yourorg.yourservice.protos/domain/order/v1/workflows.proto
package yourorg.yourservice.protos.domain.order.v1;  // ✅ matches path
```

### 4. Use `optional` for Nullable Fields

```protobuf
message OrderRequest {
    string order_id = 1;                              // Required (non-nullable)
    optional google.protobuf.Timestamp timestamp = 2; // Nullable in generated C#
    optional FulfillmentOrder order = 3;              // Nullable in generated C#
}
```

### 5. Use Google Standard Types

```protobuf
import "google/protobuf/timestamp.proto";
import "google/type/money.proto";
import "google/type/decimal.proto";
import "google/protobuf/struct.proto";

message PriceResult {
    google.protobuf.Timestamp priced_at = 1;    // Not string
    google.type.Money total = 2;                 // Not double
    google.type.Decimal quantity = 3;            // Not double (precision)
    google.protobuf.Value metadata = 4;          // Dynamic/untyped data
}
```

### 6. Request/Response Pairs

Updates and queries **must** have matching pairs:

```protobuf
message CancelOrderRequest { string reason = 1; }
message CancelOrderResponse { bool success = 1; }
```

### 7. Field Deprecation Lifecycle

Follow this 3-step process when removing or renaming fields:

```protobuf
// Step 1: Mark as deprecated (keep field in place)
message PriceResponse {
    FulfillmentFeeDetails fulfillment_fee_details = 9 [deprecated=true];
}

// Step 2: Delete the property line, reserve both name and number
message PriceResponse {
    // -- Reserved field names --
    reserved "fulfillment_fee_details";

    // -- Reserved field numbers --
    reserved 9;
}
```

Always reserve **both** the field name and number to prevent accidental reuse.

---

## Code Generation Workflow

```powershell
# 1. Lint — verify schema follows protobuf best practices
buf lint
# No output = success. Fix all errors before generating.

# 2. Check for breaking changes against main branch
buf breaking --against .git#branch=main
# No output = success. Reports any backward-incompatible changes.

# 3. Generate — produce C# models
buf generate
# No output = success. Files appear in configured output directory.

# 4. Verify — check generated files exist
Get-ChildItem src/YourProject.Core/Generated/ -Recurse -Filter "*.cs"
```

**Common lint errors:**

| Error | Fix |
|-------|-----|
| `FIELD_LOWER_SNAKE_CASE` | Use `order_id` not `OrderID` |
| `ENUM_VALUE_UPPER_SNAKE_CASE` | Use `ORDER_STATUS_PENDING` not `OrderStatusPending` |
| `ENUM_ZERO_VALUE_SUFFIX` | First enum value must end with `_UNSPECIFIED` and equal `0` |
| `PACKAGE_DIRECTORY_MATCH` | Package must match directory, or add to `ignore_only` in buf.yaml |

---

## .csproj Integration

### Making Proto Files Visible in IDE

Link proto files into the project so they appear in Solution Explorer without copying:

```xml
<ItemGroup>
  <None Include="..\..\proto\**\*">
    <Link>proto\%(RecursiveDir)%(Filename)%(Extension)</Link>
  </None>
</ItemGroup>
```

This creates a virtual `proto/` folder in the project showing all `.proto` files for navigation and editing.

### NuGet Package References

```xml
<ItemGroup>
  <PackageReference Include="Google.Api.CommonProtos" />
  <PackageReference Include="Google.Protobuf" />
  <PackageReference Include="Grpc" />
</ItemGroup>
```

Use central package management (`Directory.Packages.props`) for version pinning.

### Generated Files — Committed to Git

Generated C# files in `Generated/` are **committed to source control**, not regenerated at build time. The `.gitignore` in the Core project only excludes XML documentation:

```
# .gitignore in Core project
YourProject.Core.xml
```

Developers run `buf generate` manually after schema changes and commit the results.

---

## Generated Code Handling

**CRITICAL: Never modify files in `Generated/`** — they are overwritten on every `buf generate` run.

### Option 1: Extension Methods (Preferred)

```csharp
// Extensions/OrderExtensions.cs
public static class OrderExtensions
{
    public static bool IsValid(this OrderRequest request)
        => !string.IsNullOrEmpty(request.OrderId);
}
```

See **extensions-reference.md** for comprehensive patterns covering GoogleMoney, GoogleDecimal, Value/Struct conversions, RepeatedField helpers, and enum formatting.

### Option 2: Partial Classes

```csharp
// Domain/Order/V1/OrderRequest.Partial.cs
namespace YourProject.Core.Domain.Order.V1;

public sealed partial class OrderRequest
{
    public bool IsValid() => !string.IsNullOrEmpty(OrderId);
}
```

---

## Schema Evolution

| Change | Safe? | Notes |
|--------|-------|-------|
| Add a field | ✅ | Old code ignores; new code uses default |
| Deprecate a field | ✅ | Mark `[deprecated = true]`; wire format intact |
| Rename a field | ⚠️ | Safe for binary proto; **risky for JSON/text** |
| Remove a field | ⚠️ | Only if unused; **always reserve the number** |
| Change field type | ❌ | Different wire representation |
| Change cardinality | ❌ | `optional` ↔ `repeated` breaks compat |
| Reuse field number | ❌ | Corrupts deserialization — **never do this** |

**Strategy**: Prefer additive changes. To rename, add the new field and deprecate the old. Always reserve removed field numbers.

> **Temporal workflows**: Schema evolution directly impacts running workflow event history. Use **Replay tests** to verify compatibility. See the `temporal-versioning` skill for full guidance.

---

## Creating a New Domain Context

```powershell
# 1. Create directory structure
New-Item -ItemType Directory -Path "proto/your.namespace/domain/payment/v1" -Force

# 2. Create proto files
@("workflows.proto", "values.proto", "commands.proto", "queries.proto") | ForEach-Object {
    New-Item -ItemType File -Path "proto/your.namespace/domain/payment/v1/$_"
}

# 3. Add package header to each file
# syntax = "proto3";
# package your.namespace.domain.payment.v1;
```

Then update `buf.yaml` lint ignores if using dot-separated directory names, and run `buf lint` + `buf generate`.

---

## Verification Checklist

- [ ] Schema in versioned directory (`v1`, `v2`, etc.)
- [ ] Package name matches directory path
- [ ] Single message per request/response
- [ ] `optional` used for nullable fields
- [ ] Google standard types used (Timestamp, Money, Decimal)
- [ ] Enum values have `_UNSPECIFIED = 0` first entry
- [ ] `buf lint` passes with no errors
- [ ] `buf generate` succeeds
- [ ] Generated files appear in expected output directory
- [ ] No modifications to generated files
- [ ] Reserved numbers for any removed fields

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Editing files in `Generated/` | Use extension methods or partial classes |
| Multiple method parameters instead of single message | Wrap in a request message |
| `buf generate` before `buf lint` | Always lint first to catch schema errors |
| Missing `optional` on nullable fields | Generated C# won't match nullability expectations |
| Schema outside version directory | Always under `/v1/`, `/v2/` for upgrade path |
| Reusing a removed field number | Reserve removed field numbers and names |
| Forgetting `buf.yaml` lint ignore for dot-separated dirs | Add to `ignore_only.PACKAGE_DIRECTORY_MATCH` |
| Using JSON test data files for `Value` fields | JSON deserialization leaves `Value` as `KindCase.None`. Construct objects programmatically and call `.ToProtoBufValueFromClassInput()` — see [protobuf-value-testing.md](/docs/procedures/protobuf-value-testing.md) |
