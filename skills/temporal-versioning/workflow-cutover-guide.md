# Workflow Cutover Guide - Complete Steps

## When to Use Workflow Cutovers

Use cutovers when breaking changes are too extensive for patching (e.g., complete workflow restructure, major business logic overhaul).

## Copy-and-Freeze Pattern

**Pattern**: Copy existing workflow to frozen V1 file, modify original for new logic.

**Why**: Keeps original filename for new code, making PR diffs show actual business changes.

## Complete 7-Step Process

### Step 1: Copy Existing Workflow to Frozen Version

```bash
# Example: OrderWorkflow.workflow.cs contains current production code
cp src/Application/Workflows/OrderWorkflow.workflow.cs src/Application/Workflows/OrderWorkflowV1.workflow.cs
```

### Step 2: Version Your Models

**Critical**: Workflows use data models (DTOs, requests, responses). Version these too!

#### For Projects Using Protobuf

```bash
# Create V2 protobuf definitions
mkdir -p proto/yourorg.yourservice.protos/domain/order/v2

# Copy V1 definitions to V2
cp proto/.../domain/order/v1/*.proto proto/.../domain/order/v2/

# Update package in v2 protos
# Change: package yourorg.yourservice.protos.domain.order.v1;
# To:     package yourorg.yourservice.protos.domain.order.v2;

# Regenerate code
buf generate
```

**Result**: Generated classes in `Generated/Domain/Order/V2/`

#### For Projects NOT Using Protobuf

```bash
# Create versioned model folders
mkdir -p src/Application/Models/V1
mkdir -p src/Application/Models/V2

# Copy V1 models to versioned folder
cp src/Application/Models/OrderRequest.cs src/Application/Models/V1/
cp src/Application/Models/OrderResult.cs src/Application/Models/V1/

# Update namespaces
# V1: namespace YourOrg.YourService.Application.Models.V1;
# V2: namespace YourOrg.YourService.Application.Models.V2;
```

**Why Version Models**:
- V1 workflow replaying history needs V1 model structure
- V2 workflow with breaking changes uses V2 models
- Prevents conflicts and deserialization errors
- Clean separation between versions

### Step 3: Add Warning Comment to Frozen V1

```csharp
// ⚠️ WARNING: FROZEN LEGACY CODE - DO NOT MODIFY! ⚠️
// This is the V1 workflow for in-flight executions started before 2026-01-28.
// All modifications should go in OrderWorkflow.cs (V2).
// This file will be deleted after final V1 execution completes (~8 weeks).

[Workflow("order-fulfillment-v1")]  // ← Explicit type name for V1
public class OrderWorkflowV1
{
    [WorkflowRun]
    public async Task<OrderResult> RunAsync(OrderInput input)
    {
        // Original V1 logic preserved exactly as-is
    }
}
```

### Step 4: Register Both Workflows with Workers

```csharp
// Worker registration
using var worker = new TemporalWorker(
    client,
    new TemporalWorkerOptions("order-tasks-queue")
        .AddWorkflow<OrderWorkflowV1>()    // Handles V1 executions
        .AddWorkflow<OrderWorkflow>());    // Handles V2 executions
```

### Step 5: Modify Original File for V2 Logic

```csharp
// OrderWorkflow.cs - New V2 implementation
// WorkflowTypeName attribute determines Temporal routing, NOT class name
[Workflow("order-fulfillment")]  // ← No version suffix - this is active version
public class OrderWorkflow
{
    [WorkflowRun]
    public async Task<OrderResult> RunAsync(OrderInput input)
    {
        // NEW V2 logic here - complete rewrite allowed
    }
}
```

**Critical**: `WorkflowTypeName` determines routing. Queries use `"order-fulfillment"` or `"order-fulfillment-v1"`, NOT class names.

### Step 6: Update Workflow Starters (If Needed)

Most starters use WorkflowTypeName from `[Workflow]` attribute automatically - no change needed.

If you have explicit type name parameters, ensure they target correct version:
- New executions: `"order-fulfillment"` (V2)
- Manual V1 starts: `"order-fulfillment-v1"` (rare)

### Step 7: Deploy in Sequence

```bash
# 1. Deploy workers with BOTH workflows registered (Step 3)
#    - V1 executions continue on OrderWorkflowV1 class
#    - V2 executions start on OrderWorkflow class

# 2. Deploy starters to create new V2 executions (Step 5)

# 3. Wait for all V1 executions to complete (check Temporal UI)
temporal workflow list --query 'WorkflowType="order-fulfillment-v1" AND ExecutionStatus="Running"'

# 4. Monitor: V1 count drops to zero over 4-8 weeks
```

### Step 8: Cleanup After V1 Retirement

Once final V1 execution completes:

```bash
# 1. Remove V1 workflow file
rm src/Application/Workflows/OrderWorkflowV1.workflow.cs

# 2. Remove V1 models
# Protobuf: rm -r proto/.../domain/order/v1/ (regenerate)
# Non-protobuf: rm -r src/Application/Models/V1/

# 3. Remove V1 from worker registration
# (Only .AddWorkflow<OrderWorkflow>() remains)

# 4. Deploy cleanup
```

**Final state**: 
- Only `OrderWorkflow.cs` exists
- Only V2 models remain
- All new executions use V2

## Timeline Example

**Week 1**: Copy to V1, modify V2, deploy both  
**Weeks 2-8**: V1 executions gradually complete, V2 handles all new starts  
**Week 9**: Last V1 execution finishes, delete V1 file

## What Happens to In-Flight Workflows

### Timeline with Copy-and-Freeze

```
Before cutover:
  ✅ OrderWorkflow.cs [Workflow("order-fulfillment")] - handles all executions

After Step 1-3 (copy and register):
  ✅ OrderWorkflowV1.cs [Workflow("order-fulfillment-v1")] - FROZEN, handles old executions
  ✅ OrderWorkflow.cs [Workflow("order-fulfillment")] - handles all executions (no change yet)

After Step 4 (modify original):
  ✅ OrderWorkflowV1.cs [Workflow("order-fulfillment-v1")] - FROZEN, handles old executions
  ✅ OrderWorkflow.cs [Workflow("order-fulfillment")] - NEW V2 logic, handles new executions

After Step 7 (cleanup):
  ✅ OrderWorkflow.cs [Workflow("order-fulfillment")] - only file, handles all executions
```

**Key insight**: In-flight workflows continue using V1 code from `OrderWorkflowV1.cs` based on their recorded WorkflowType name in history.

## Cutover Gotchas

### 1. Accidentally Modifying Frozen V1 Code

**Problem**: Developer sees OrderWorkflowV1.cs, thinks "this is old version", makes hotfix there.

**Result**: Changes lost when V1 deleted. Worse: V1 executions get untested changes.

**Prevention**: 
```csharp
// ⚠️ WARNING: FROZEN LEGACY CODE - DO NOT MODIFY! ⚠️
```

Add this comment prominently at top of V1 file.

### 2. Searching by Filename Instead of WorkflowType

**Problem**: `grep "OrderWorkflow"` returns both files, unclear which is active.

**Fix**: Always search by WorkflowType attribute:
```bash
# Find V1 workflows
grep -r 'Workflow("order-fulfillment-v1")'

# Find active/V2 workflows
grep -r 'Workflow("order-fulfillment")' --exclude="*V1*"
```

### 3. Deploying One Without the Other

**Problem**: Deploy V2 starter changes before workers support V2.

**Result**: Starters create V2 executions, workers can't find handler.

**Fix**: Always deploy workers BEFORE starters (Step 6).

### 4. Forgetting to Wait for V1 Retirement

**Problem**: Delete V1 file while executions still running.

**Result**: V1 executions fail with "Workflow type not registered".

**Fix**: Query Temporal for running V1 executions before cleanup:
```bash
temporal workflow list --query 'WorkflowType="order-fulfillment-v1" AND ExecutionStatus="Running"'
```

Only proceed with Step 8 when count is zero.

### 5. Forgetting to Version Models

**Problem**: V1 and V2 workflows both use `OrderRequest` model from same namespace.

**Result**: 
- V2 workflow changes model structure (adds required field)
- V1 workflow replaying history fails to deserialize old events
- `SerializationException` or `InvalidCastException`

**Solution**: Always version models in separate folders/namespaces
```csharp
// V1 workflow
using YourOrg.YourService.Application.Models.V1;  // V1 models

// V2 workflow  
using YourOrg.YourService.Application.Models.V2;  // V2 models
```

**For Protobuf**: Version proto package names
```protobuf
// v1/commands.proto
package yourorg.yourservice.protos.domain.order.v1;

// v2/commands.proto
package yourorg.yourservice.protos.domain.order.v2;
```

## Complete Example

See main SKILL.md for condensed example. This guide provides the full implementation details.
