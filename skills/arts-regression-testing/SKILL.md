---
name: arts-regression-testing
description: >-
  Automated Regression Test Suite (ARTS) — a complete reference architecture for building
  black-box, environment-targeted regression tests for .NET microservices. Covers xUnit v3
  assembly fixtures, Temporal workflow-driven testing, golden-file comparisons, helper patterns,
  and CI/CD pipeline integration.
---

# ARTS — Automated Regression Test Suite

> **Purpose:** Provide a reproducible blueprint for building production-grade regression test
> suites that run against real deployed environments, gate deployments, and catch contract
> breaks before they reach users.

---

## Philosophy

ARTS is not unit testing. It is not integration testing. It is **live-environment validation**.

| Principle | What it means |
|-----------|---------------|
| Black-box | Tests interact ONLY through the service's public surface — HTTP endpoints, message topics, workflow signals, Nexus operations. Never reference internal classes. |
| Environment-targeted | The SUT (System Under Test) is a real deployed instance. ARTS never starts the service in-process. |
| Deterministic | Every test generates unique test data. No shared state. No ordering dependencies. |
| Idempotent | Safe to re-run without cleanup scripts. |
| Contract-focused | Assert on observable outputs — responses, events produced, documents written, workflow milestones. |
| Deployment-gating | Runs after deploy to a pre-production environment. Promotion to production is blocked on failure. |
| Diagnosable | Captures workflow histories, request/response pairs, and timing for post-mortem analysis. |

---

## Project Structure

```
src/
├── YourService.Api/
├── YourService.Worker/
└── ...
tests/
├── YourService.Tests/              ← Unit tests (in-process, mocked)
├── YourService.IntegrationTests/   ← Testcontainers (local, containerized)
└── YourService.Regression.Test/    ← ARTS (live environment, black-box)
    ├── YourService.Regression.Test.sln   ← Dedicated solution
    ├── YourService.Regression.Test.csproj
    ├── Fixtures/
    │   ├── AssemblyFixture.cs            ← Lifecycle: environment, workers, browsers
    │   └── TestCollection.cs             ← xUnit collection linking fixture
    ├── Helpers/
    │   ├── ServiceHelper.cs              ← Request builders, field mutation, assertion exclusions
    │   └── WaitHelper.cs                 ← Condition-based polling helpers
    ├── TestData/
    │   └── Scenarios/                    ← Golden JSON files (canonical requests per scenario)
    ├── TestResults/
    │   └── WorkflowHistories/            ← Captured histories for debugging (gitignored)
    ├── Tests/
    │   ├── HappyPath/
    │   │   ├── BasicFlowTests.cs
    │   │   └── MultiStepFlowTests.cs
    │   ├── EdgeCases/
    │   │   └── TimeoutRecoveryTests.cs
    │   └── Contracts/
    │       └── ResponseSchemaTests.cs
    └── appsettings.json                  ← Target env URLs, auth config (no secrets!)
        appsettings.Cert.json
        appsettings.Production.json       ← (Optional — read-only smoke tests)
```

---

## Core Components

### 1. Assembly Fixture (xUnit v3)

The assembly fixture owns the **entire test lifecycle**. It starts once per test run and tears down after all tests complete.

```csharp
using Xunit;

[assembly: AssemblyFixture(typeof(RegressionTestFixture))]

namespace YourService.Regression.Test.Fixtures;

/// <summary>
/// Owns all shared infrastructure for the regression suite:
/// - Temporal test environment (local or cloud namespace)
/// - Service worker host (if testing workflows locally)
/// - HTTP clients with auth
/// - Workflow history capture
/// - Cleanup of test data
/// </summary>
public sealed class RegressionTestFixture : IAsyncLifetime
{
    public HttpClient AuthenticatedClient { get; private set; } = null!;
    public ITemporalClient TemporalClient { get; private set; } = null!;
    public WorkflowHistoryCapture HistoryCapture { get; private set; } = null!;
    
    // Optional: local Temporal environment for replay tests
    public IWorkflowEnvironment? LocalEnvironment { get; private set; }
    
    public async ValueTask InitializeAsync()
    {
        // 1. Load configuration (target environment URLs, auth)
        var config = LoadConfiguration();
        
        // 2. Set up authenticated HTTP client
        AuthenticatedClient = CreateAuthenticatedClient(config);
        
        // 3. Connect to Temporal namespace (cloud or local)
        TemporalClient = await ConnectToTemporal(config);
        
        // 4. Initialize workflow history capture (for diagnostics)
        HistoryCapture = new WorkflowHistoryCapture(outputDirectory: "TestResults/WorkflowHistories");
        
        // 5. (Optional) Start local Temporal workers for isolated scenarios
        // LocalEnvironment = await WorkflowEnvironment.StartLocalAsync();
    }
    
    public async ValueTask DisposeAsync()
    {
        // Cleanup: cancel any lingering test workflows
        await CleanupTestWorkflows();
        AuthenticatedClient.Dispose();
    }
    
    private async Task CleanupTestWorkflows()
    {
        // Find all workflows with test prefix and terminate them
        var query = $"WorkflowId STARTS_WITH 'ARTS-'";
        // Use visibility API to find and terminate stale test workflows
    }
}
```

### 2. Test Collection

```csharp
namespace YourService.Regression.Test;

[CollectionDefinition("Regression")]
public class RegressionTestCollection : ICollectionFixture<RegressionTestFixture> { }
```

### 3. Helper Pattern

The helper centralizes request construction, scenario-specific mutations, and assertion logic.

```csharp
namespace YourService.Regression.Test.Helpers;

public class ServiceHelper
{
    private readonly HttpClient _client;
    private readonly ITemporalClient _temporal;
    
    public ServiceHelper(RegressionTestFixture fixture)
    {
        _client = fixture.AuthenticatedClient;
        _temporal = fixture.TemporalClient;
    }
    
    /// <summary>
    /// Loads a canonical request from TestData, mutates scenario-specific fields,
    /// and returns a ready-to-send request body.
    /// </summary>
    public T LoadScenario<T>(string scenarioName, Action<T>? mutate = null)
    {
        var json = File.ReadAllText($"TestData/Scenarios/{scenarioName}.json");
        var request = JsonSerializer.Deserialize<T>(json)!;
        mutate?.Invoke(request);
        return request;
    }
    
    /// <summary>
    /// Generates a unique test ID with the ARTS prefix for easy identification.
    /// </summary>
    public string GenerateTestId(string scenario)
        => $"ARTS-{scenario}-{Guid.NewGuid():N[..8]}";
    
    /// <summary>
    /// Asserts response matches expected, excluding volatile fields (timestamps, IDs).
    /// </summary>
    public void AssertResponseMatches<T>(T actual, T expected, params string[] excludeFields)
    {
        var options = new JsonSerializerOptions { WriteIndented = true };
        var actualJson = JsonDocument.Parse(JsonSerializer.Serialize(actual, options));
        var expectedJson = JsonDocument.Parse(JsonSerializer.Serialize(expected, options));
        
        // Deep comparison excluding volatile fields
        AssertJsonEquivalent(actualJson, expectedJson, excludeFields);
    }
}
```

### 4. Wait Helper (Condition-Based Polling)

**Never use `Thread.Sleep` or `Task.Delay` with hardcoded values.** Always poll for conditions.

```csharp
namespace YourService.Regression.Test.Helpers;

public static class WaitHelper
{
    /// <summary>
    /// Polls a condition until true or timeout. Preferred over fixed delays.
    /// </summary>
    public static async Task<T> WaitForConditionAsync<T>(
        Func<Task<T>> check,
        Func<T, bool> condition,
        TimeSpan timeout,
        TimeSpan pollInterval,
        string timeoutMessage = "Condition not met within timeout")
    {
        var deadline = DateTime.UtcNow + timeout;
        while (DateTime.UtcNow < deadline)
        {
            var result = await check();
            if (condition(result)) return result;
            await Task.Delay(pollInterval);
        }
        throw new TimeoutException(timeoutMessage);
    }
    
    /// <summary>
    /// Waits for a workflow to reach a specific status.
    /// </summary>
    public static async Task<WorkflowExecution> WaitForWorkflowStatus(
        ITemporalClient client,
        string workflowId,
        WorkflowExecutionStatus targetStatus,
        TimeSpan? timeout = null)
    {
        return await WaitForConditionAsync(
            check: async () => await client.GetWorkflowAsync(workflowId),
            condition: wf => wf.Status == targetStatus,
            timeout: timeout ?? TimeSpan.FromSeconds(60),
            pollInterval: TimeSpan.FromSeconds(2),
            timeoutMessage: $"Workflow {workflowId} did not reach {targetStatus}");
    }
    
    /// <summary>
    /// Waits for a message to appear on a topic/queue.
    /// </summary>
    public static async Task<TMessage> WaitForMessage<TMessage>(
        IMessageConsumer consumer,
        Func<TMessage, bool> predicate,
        TimeSpan? timeout = null)
    {
        return await WaitForConditionAsync(
            check: () => consumer.TryConsumeAsync<TMessage>(),
            condition: msg => msg != null && predicate(msg),
            timeout: timeout ?? TimeSpan.FromSeconds(30),
            pollInterval: TimeSpan.FromMilliseconds(500),
            timeoutMessage: $"Expected message of type {typeof(TMessage).Name} not received");
    }
}
```

### 5. Workflow History Capture

```csharp
namespace YourService.Regression.Test.Helpers;

/// <summary>
/// Captures workflow histories after each test for diagnostics and replay regression.
/// These histories can later be used as replay test inputs.
/// </summary>
public class WorkflowHistoryCapture
{
    private readonly string _outputDirectory;
    
    public WorkflowHistoryCapture(string outputDirectory)
    {
        _outputDirectory = outputDirectory;
        Directory.CreateDirectory(outputDirectory);
    }
    
    /// <summary>
    /// Captures the full workflow history as JSON for post-mortem analysis.
    /// Also serves as input for future replay regression tests.
    /// </summary>
    public async Task CaptureAsync(
        ITemporalClient client,
        string workflowId,
        string testName)
    {
        var history = await client.GetWorkflowHistoryAsync(workflowId);
        var json = JsonSerializer.Serialize(history, new JsonSerializerOptions { WriteIndented = true });
        
        var filename = $"{testName}_{DateTime.UtcNow:yyyyMMdd_HHmmss}.json";
        await File.WriteAllTextAsync(Path.Combine(_outputDirectory, filename), json);
    }
}
```

---

## Test Patterns

### Pattern 1: HTTP Endpoint Regression

```csharp
[Collection("Regression")]
[Trait("Category", "Arts")]
[Trait("Tier", "Smoke")]
public class OrderSubmitTests
{
    private readonly ServiceHelper _helper;
    private readonly RegressionTestFixture _fixture;
    
    public OrderSubmitTests(RegressionTestFixture fixture)
    {
        _fixture = fixture;
        _helper = new ServiceHelper(fixture);
    }
    
    [Fact]
    public async Task SubmitOrder_StandardCheckout_ReturnsAccepted()
    {
        // Arrange
        var testId = _helper.GenerateTestId("standard-checkout");
        var request = _helper.LoadScenario<SubmitOrderRequest>("standard-checkout", r =>
        {
            r.OrderId = testId;
            r.CustomerId = "test-customer-001";
        });
        
        // Act
        var response = await _fixture.AuthenticatedClient.PostAsJsonAsync("/api/v1/orders", request);
        
        // Assert — contract-level only
        response.StatusCode.Should().Be(HttpStatusCode.Accepted);
        var body = await response.Content.ReadFromJsonAsync<SubmitOrderResponse>();
        body!.OrderId.Should().Be(testId);
        body.Status.Should().Be("Submitted");
    }
}
```

### Pattern 2: Workflow-Driven Testing (Temporal/Nexus)

For services orchestrated by workflows, tests drive behavior through the workflow's public interface — signals, updates, queries, or Nexus operations.

```csharp
[Collection("Regression")]
[Trait("Category", "Arts")]
[Trait("Tier", "Regression")]
public class WorkflowRegressionTests
{
    private readonly RegressionTestFixture _fixture;
    private readonly ServiceHelper _helper;
    
    public WorkflowRegressionTests(RegressionTestFixture fixture)
    {
        _fixture = fixture;
        _helper = new ServiceHelper(fixture);
    }
    
    [Fact]
    public async Task ProcessWorkflow_HappyPath_CompletesSuccessfully()
    {
        // Arrange
        var testId = _helper.GenerateTestId("happy-path");
        var input = _helper.LoadScenario<WorkflowInput>("happy-path", i => i.EntityId = testId);
        
        // Act — start the workflow via its public API or signal
        var handle = await _fixture.TemporalClient.StartWorkflowAsync(
            "YourWorkflow",
            input,
            new WorkflowOptions { Id = $"ARTS-{testId}", TaskQueue = "your-task-queue" });
        
        // Wait for completion (condition-based, not fixed delay)
        var result = await WaitHelper.WaitForWorkflowStatus(
            _fixture.TemporalClient,
            handle.Id,
            WorkflowExecutionStatus.Completed,
            timeout: TimeSpan.FromMinutes(2));
        
        // Assert
        result.Should().NotBeNull();
        
        // Capture history for diagnostics / future replay tests
        await _fixture.HistoryCapture.CaptureAsync(
            _fixture.TemporalClient, handle.Id, nameof(ProcessWorkflow_HappyPath_CompletesSuccessfully));
    }
    
    [Fact]
    public async Task ProcessWorkflow_PartialFailure_CompensatesCorrectly()
    {
        // Arrange
        var testId = _helper.GenerateTestId("compensation");
        var input = _helper.LoadScenario<WorkflowInput>("partial-failure", i => i.EntityId = testId);
        
        // Act — trigger workflow that will partially fail
        var handle = await _fixture.TemporalClient.StartWorkflowAsync(
            "YourWorkflow",
            input,
            new WorkflowOptions { Id = $"ARTS-{testId}", TaskQueue = "your-task-queue" });
        
        // Wait for the workflow to reach compensated state
        var finalState = await WaitHelper.WaitForConditionAsync(
            check: () => _fixture.TemporalClient.QueryWorkflowAsync<string>(handle.Id, "GetStatus"),
            condition: status => status == "Compensated" || status == "Failed",
            timeout: TimeSpan.FromMinutes(3),
            pollInterval: TimeSpan.FromSeconds(5));
        
        // Assert compensation happened
        finalState.Should().Be("Compensated");
        
        // Verify downstream effects (events produced, documents cleaned up)
        // ...
    }
}
```

### Pattern 3: Golden File Comparison

Golden files store "known-good" request/response pairs. Tests load them, execute, and compare.

```csharp
[Fact]
[Trait("Tier", "Regression")]
public async Task GetEntity_KnownScenario_MatchesGoldenResponse()
{
    // Arrange — load golden request and expected response
    var request = _helper.LoadScenario<GetEntityRequest>("known-entity");
    var expectedResponse = JsonSerializer.Deserialize<GetEntityResponse>(
        File.ReadAllText("TestData/Scenarios/known-entity.expected.json"));
    
    // Act
    var response = await _fixture.AuthenticatedClient
        .GetFromJsonAsync<GetEntityResponse>($"/api/v1/entities/{request.Id}");
    
    // Assert — compare excluding volatile fields
    _helper.AssertResponseMatches(
        response!, 
        expectedResponse!,
        excludeFields: ["timestamp", "lastModified", "correlationId"]);
}
```

### Pattern 4: Messaging Assertion

```csharp
[Fact]
[Trait("Tier", "Regression")]
public async Task TriggerAction_ProducesExpectedEvent()
{
    // Arrange — subscribe to the output topic BEFORE triggering
    using var consumer = _fixture.CreateTestConsumer("your.domain.events");
    await consumer.SubscribeAsync();
    
    var testId = _helper.GenerateTestId("event-production");
    
    // Act — trigger the action that should produce a message
    await _fixture.AuthenticatedClient.PostAsJsonAsync("/api/v1/actions", new { EntityId = testId });
    
    // Assert — wait for the event (condition-based)
    var message = await WaitHelper.WaitForMessage<DomainEvent>(
        consumer,
        predicate: e => e.EntityId == testId && e.Type == "ActionCompleted",
        timeout: TimeSpan.FromSeconds(30));
    
    message.Should().NotBeNull();
    message.EntityId.Should().Be(testId);
}
```

---

## Golden File Management

### Directory Convention

```
TestData/
└── Scenarios/
    ├── standard-checkout.json           ← Input request
    ├── standard-checkout.expected.json  ← Expected response (optional)
    ├── partial-failure.json
    ├── edge-case-timeout.json
    └── README.md                        ← Documents each scenario
```

### Rules

1. **One file per scenario** — named after the behavior being tested
2. **Canonical fields only** — test-specific mutations happen in code via `LoadScenario<T>(name, mutate)`
3. **Never commit volatile values** — timestamps, generated IDs, or correlation IDs belong in `excludeFields`
4. **Version with the code** — golden files change when contracts change (intentionally)
5. **Review golden file diffs in PRs** — a changed golden file IS the contract change documentation

---

## Test ID Convention

All ARTS-generated data uses a recognizable prefix:

```
ARTS-{scenario}-{unique-suffix}
```

Examples:
- `ARTS-standard-checkout-a1b2c3d4`
- `ARTS-compensation-flow-e5f6g7h8`
- `ARTS-timeout-recovery-i9j0k1l2`

This enables:
- Ops teams can identify and ignore test data in production metrics
- Cleanup scripts can target `ARTS-*` entities
- Monitoring dashboards can filter test traffic

---

## CI/CD Pipeline Integration

### Pipeline Stage (runs after deploy, before promotion)

```yaml
# GitHub Actions example
regression-tests:
  needs: deploy-to-cert
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    
    - name: Setup .NET
      uses: actions/setup-dotnet@v4
      with:
        dotnet-version: '8.0.x'
    
    - name: Run ARTS Smoke Tests
      run: |
        dotnet test tests/YourService.Regression.Test/ \
          --filter "Tier=Smoke" \
          --configuration Release \
          --logger "trx;LogFileName=arts-smoke.trx"
      env:
        TARGET_ENVIRONMENT: cert
        AUTH_TOKEN: ${{ secrets.CERT_AUTH_TOKEN }}
    
    - name: Run ARTS Full Regression
      if: success()
      run: |
        dotnet test tests/YourService.Regression.Test/ \
          --filter "Tier=Regression" \
          --configuration Release \
          --logger "trx;LogFileName=arts-regression.trx"
      env:
        TARGET_ENVIRONMENT: cert
        AUTH_TOKEN: ${{ secrets.CERT_AUTH_TOKEN }}
    
    - name: Upload Test Results
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: arts-results
        path: |
          **/arts-*.trx
          **/TestResults/WorkflowHistories/

# ADO Pipeline equivalent
# - stage: ARTS
#   dependsOn: DeployToCert
#   jobs:
#   - job: RegressionTests
#     steps:
#     - task: DotNetCoreCLI@2
#       inputs:
#         command: test
#         arguments: '--filter "Tier=Smoke"'
```

### Tier Strategy

| Tier | When it runs | Timeout | Blocks promotion |
|------|-------------|---------|-----------------|
| `Smoke` | Every deploy to any environment | 5 min | Yes |
| `Regression` | Deploy to pre-prod (CERT) | 15 min | Yes |
| `Extended` | Nightly or on-demand | 60 min | No (alerts only) |

---

## Configuration

### appsettings.json (committed — no secrets)

```json
{
  "TargetEnvironment": {
    "BaseUrl": "https://your-service.cert.internal",
    "TemporalNamespace": "your-namespace.cert",
    "TemporalAddress": "your-temporal-cloud:7233",
    "KafkaBrokers": "kafka-cert.internal:9092"
  },
  "TestSettings": {
    "DefaultTimeoutSeconds": 60,
    "PollIntervalMs": 2000,
    "TestIdPrefix": "ARTS",
    "CaptureWorkflowHistories": true
  }
}
```

### Secrets (from Key Vault or CI/CD variables — NEVER committed)

- `AUTH_TOKEN` — service-to-service auth token for the target environment
- `TEMPORAL_TLS_CERT` — mTLS cert for Temporal Cloud connection
- `KAFKA_SASL_PASSWORD` — if Kafka requires auth

---

## Anti-Patterns

| ❌ Don't | ✅ Do Instead |
|-----------|--------------|
| `Thread.Sleep(5000)` | `WaitHelper.WaitForConditionAsync(...)` |
| Reference internal classes | Use only public HTTP/gRPC/Nexus APIs |
| Share state between tests | Generate unique `ARTS-` IDs per test |
| Hard-code URLs or secrets | Use `appsettings.{env}.json` + Key Vault |
| Assert on internal fields | Assert on public contract outputs |
| Run against local-only services | Target a real deployed environment |
| Skip cleanup of long-running workflows | Terminate `ARTS-*` workflows in fixture teardown |
| Use `[Theory]` with 50 inline cases | Use one focused `[Fact]` per critical path |
| Put ARTS tests in the unit test project | Dedicated `*.Regression.Test` project |

---

## Setting Up ARTS for a New Service

### Checklist

1. **Create the project**
   ```bash
   dotnet new xunit -n YourService.Regression.Test
   dotnet new sln -n YourService.Regression.Test
   dotnet sln add YourService.Regression.Test.csproj
   ```

2. **Add required packages**
   ```xml
   <PackageReference Include="xunit" Version="2.9+" />
   <PackageReference Include="xunit.runner.visualstudio" Version="2.8+" />
   <PackageReference Include="FluentAssertions" Version="7+" />
   <PackageReference Include="Microsoft.Extensions.Configuration" Version="8+" />
   <PackageReference Include="Microsoft.Extensions.Configuration.Json" Version="8+" />
   <PackageReference Include="Microsoft.Extensions.Http" Version="8+" />
   <!-- Add Temporal, Kafka, or other client packages as needed -->
   ```

3. **Create the assembly fixture** (see pattern above)

4. **Create your first smoke test** — the primary happy path of the service

5. **Create the golden file** — save a canonical request that exercises the happy path

6. **Wire the pipeline**
   - Add a `regression-tests` stage after deploy
   - Configure secrets (auth token, TLS certs)
   - Set failure to block promotion

7. **Document it** — add a section to the service's architecture docs explaining what the ARTS suite covers

### First Test Rule

The first ARTS test for any service should be:

> **"The primary happy path works end-to-end when the service is freshly deployed."**

This catches deployment configuration issues, missing environment variables, broken secrets, and infrastructure drift.

---

## From ARTS to Replay Regression

ARTS tests capture workflow histories. These histories become **replay regression tests**:

1. ARTS test runs → captures `TestResults/WorkflowHistories/happy-path_20260115.json`
2. Developer copies history to `TestData/ReplayHistories/`
3. Replay test loads history and replays against current code
4. If code change breaks determinism → replay fails → code change is caught pre-merge

```csharp
[Fact]
[Trait("Category", "Replay")]
public async Task ReplayHappyPath_CurrentCode_Succeeds()
{
    var history = await File.ReadAllTextAsync("TestData/ReplayHistories/happy-path_20260115.json");
    
    // Replay the recorded history against current workflow code
    await WorkflowReplayer.ReplayWorkflowAsync<YourWorkflow>(history);
    
    // If this doesn't throw, current code is backward-compatible with recorded execution
}
```

This creates a **feedback loop**: ARTS validates behavior → captures proof → proof becomes future regression gate.

---

## Council Integration

- **Test Lead** owns the ARTS pattern and ensures every deliverable has regression coverage
- **Workflow Lead** owns Temporal-specific replay tests (hands off to Test Lead for non-workflow assertions)
- **DevOps Lead** owns pipeline wiring (stages, secrets, promotion gates)
- **Quality Analyst** reviews ARTS test code quality (no magic strings, proper waits, clean assertions)

When Test Lead is invoked on a feature: *"What's the ARTS coverage for this change?"*

If the answer is "none," that is part of the work — not a separate ticket.

---

*← Back to [Council README](../../README.md)*
