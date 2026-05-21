---
name: aspire-local-testing
description: "Use when running local E2E tests with .NET Aspire AppHost — starting the Aspire dashboard, producing Kafka test messages via docker exec, executing Temporal workflows against emulated containers, verifying Cosmos DB state in the emulator, importing Cosmos emulator SSL certificates, or troubleshooting container connectivity issues"
---

# Local E2E Testing with .NET Aspire

Run end-to-end tests against Aspire-orchestrated infrastructure. Covers starting the AppHost, verifying containers, producing Kafka messages, interacting with Temporal, and inspecting Cosmos DB state.

## When to Use

- Running local E2E tests with Aspire-managed containers
- Producing test messages to Kafka via `docker exec`
- Starting/querying Temporal workflows in the emulator
- Inspecting Cosmos DB documents in the emulator
- Fixing SSL certificate errors for Cosmos DB emulator
- Debugging container connectivity (Kafka PLAINTEXT vs SASL, Temporal gRPC)
- Using the Aspire Dashboard to trace requests across services

## Startup

### 1. Start AppHost

```powershell
cd src/YourService.AppHost
dotnet run
```

The Aspire Dashboard URL appears in the console output:
```
Login to the dashboard at http://localhost:15120/login?t=<token>
```

Open that URL — it shows all resources, logs, traces, and metrics.

### 2. Verify Containers

```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

Expected containers (names vary by AppHost config):
| Container | Ports | Purpose |
|-----------|-------|---------|
| `kafka-*` | `9092`, `29092` | Kafka broker (KRaft mode) |
| `schema-registry-*` | `8081` | Confluent Schema Registry |
| `control-center-*` | `9021` | Kafka UI (optional) |
| `temporal-*` | `7233` | Temporal server |
| `cosmos-*` | `10250`, `10251` | Cosmos DB emulator |

### 3. Wait for Readiness

Containers take 30-60 seconds. Check the Aspire Dashboard — all resources should show **Running** (green).

Cosmos DB emulator is the slowest — wait for the data explorer at `https://localhost:10251/_explorer/index.html`.

## Kafka Testing

### Listener Architecture

Kafka runs two listeners — use the correct one depending on WHERE you're connecting from:

| Listener | Address | Protocol | Use From |
|----------|---------|----------|----------|
| PLAINTEXT | `kafka:29092` | No auth | Inside Docker (other containers) |
| EXTERNAL_SASL | `localhost:9092` | SASL | Host machine (your service, tools) |

**Your .NET service** connects via `localhost:9092` (configured by `WithKafkaReference`).
**Schema Registry and Control Center** connect via `kafka:29092` (internal Docker network).

### Produce Test Messages

Find the Kafka container name:
```powershell
docker ps --filter "ancestor=confluentinc/cp-server:7.9.2" --format "{{.Names}}"
```

Produce a JSON message to a topic:
```powershell
# Pipe JSON through docker exec to kafka-console-producer
# Use the PLAINTEXT listener (29092) since we're executing INSIDE the container
echo '{"key":"value","orderId":"12345"}' | docker exec -i <kafka-container> kafka-console-producer --bootstrap-server localhost:29092 --topic your-topic-name
```

For messages with a key (required for keyed consumers):
```powershell
echo 'order-123:{"orderId":"order-123","status":"submitted"}' | docker exec -i <kafka-container> kafka-console-producer --bootstrap-server localhost:29092 --topic your-topic-name --property "parse.key=true" --property "key.separator=:"
```

### Consume Messages (Debugging)

Read messages from a topic to verify they were produced:
```powershell
docker exec <kafka-container> kafka-console-consumer --bootstrap-server localhost:29092 --topic your-topic-name --from-beginning --max-messages 5
```

### List Topics

```powershell
docker exec <kafka-container> kafka-topics --bootstrap-server localhost:29092 --list
```

### Create Topics

Topics are auto-created on first produce, but you can pre-create:
```powershell
docker exec <kafka-container> kafka-topics --bootstrap-server localhost:29092 --create --topic your-topic-name --partitions 1 --replication-factor 1
```

### Confluent Control Center

If `UseKafkaEmulatorUi` is enabled, open `http://localhost:9021` to:
- Browse topics and messages
- View consumer group lag
- Monitor broker health

## Temporal Testing

### Find Temporal Container

```powershell
docker ps --filter "ancestor=temporalio/auto-setup" --format "{{.Names}}"
```

### Start a Workflow

```powershell
docker exec <temporal-container> temporal workflow start `
  --task-queue "your-task-queue" `
  --type "YourWorkflowName" `
  --workflow-id "test-workflow-001" `
  --input '{"orderId":"12345"}'
```

### Describe Workflow Status

```powershell
docker exec <temporal-container> temporal workflow describe `
  --workflow-id "test-workflow-001"
```

### View Workflow History

```powershell
docker exec <temporal-container> temporal workflow show `
  --workflow-id "test-workflow-001"
```

### Send Signal to Workflow

```powershell
docker exec <temporal-container> temporal workflow signal `
  --workflow-id "test-workflow-001" `
  --name "YourSignalName" `
  --input '{"status":"completed"}'
```

### Query Workflow State

```powershell
docker exec <temporal-container> temporal workflow query `
  --workflow-id "test-workflow-001" `
  --name "YourQueryName"
```

### List Workflows

```powershell
docker exec <temporal-container> temporal workflow list
```

### Temporal UI

The Temporal server container exposes a web UI at `http://localhost:8233` — browse namespaces, workflows, and event history.

## Cosmos DB Emulator

### SSL Certificate Setup (First Time Only)

The Cosmos DB emulator uses a self-signed certificate. Your .NET service needs it trusted:

**Option 1 — Import from running container:**
```powershell
# Export the emulator's cert
$cert = Invoke-WebRequest -Uri "https://localhost:10251/_explorer/emulator.pem" -SkipCertificateCheck
Set-Content -Path "$env:TEMP\cosmosdb-emulator.pem" -Value $cert.Content

# Import to Windows cert store
Import-Certificate -FilePath "$env:TEMP\cosmosdb-emulator.pem" -CertStoreLocation Cert:\CurrentUser\Root
```

**Option 2 — Disable SSL validation (dev only):**
```csharp
// In your service's startup, when CosmosGatewayMode is set
var clientOptions = new CosmosClientOptions
{
    ConnectionMode = ConnectionMode.Gateway,
    HttpClientFactory = () => new HttpClient(
        new HttpClientHandler { ServerCertificateCustomValidationCallback = (_, _, _, _) => true })
};
```

### Data Explorer

Open `https://localhost:10251/_explorer/index.html` to browse databases, containers, and documents.

### Create Database and Containers

The emulator starts empty. Create resources via Data Explorer or programmatically:

```csharp
var client = new CosmosClient(connectionString);
var database = await client.CreateDatabaseIfNotExistsAsync("your-database");
await database.Database.CreateContainerIfNotExistsAsync("your-container", "/partitionKey");
```

### Seed Data

For E2E tests, seed required documents before testing. Use the Cosmos SDK or Data Explorer to insert test data.

### Connection String

The emulator connection is injected by Aspire's `WithCosmosDbReference`. The standard emulator endpoint is:
```
AccountEndpoint=https://localhost:10250/;AccountKey=C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==
```

## Aspire Dashboard

The dashboard at `http://localhost:15120` provides:

| Tab | Shows |
|-----|-------|
| **Resources** | All containers and projects with status (Running/Stopped/Failed) |
| **Console** | Live stdout/stderr from each resource |
| **Structured Logs** | Structured log entries from .NET services |
| **Traces** | Distributed traces across service boundaries |
| **Metrics** | Runtime metrics (requests, latency, errors) |

### Tracing a Request

1. Produce a Kafka message or call an API endpoint
2. Open **Traces** tab in the dashboard
3. Find the trace by timestamp or operation name
4. Click to see the full distributed trace across services

### Viewing Container Logs

1. Open **Console** tab
2. Select the container (e.g., `kafka`, `temporal`)
3. View real-time logs — useful for debugging message processing issues

## E2E Test Execution Pattern

1. **Start AppHost** → `dotnet run` from AppHost project
2. **Wait for containers** → All resources green in Dashboard
3. **Seed data** → Create Cosmos databases/containers, Temporal namespaces
4. **Produce test message** → `docker exec` Kafka producer or API call
5. **Observe** → Watch Dashboard traces, structured logs, console output
6. **Verify** → Check Cosmos documents, Temporal workflow state, API responses
7. **Iterate** → Modify service code, hot-reload picks up changes

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Connecting to `localhost:29092` from host | Use `localhost:9092` from host; `kafka:29092` is container-internal |
| Cosmos SSL errors `The remote certificate is invalid` | Import emulator cert or disable SSL validation (dev only) |
| `No such container` when running `docker exec` | Container names include random suffixes — use `docker ps` to find exact name |
| Temporal workflow not picked up | Verify task queue name matches worker registration exactly |
| Kafka consumer not receiving messages | Check consumer group, topic name, and that `auto.offset.reset=earliest` for first consume |
| Containers keep restarting | Check Aspire Dashboard console for error logs; ensure ports aren't already bound |
| Schema Registry errors `Subject not found` | Auto-register schemas or pre-register before producing. Check `auto.register.schemas=true` |
| Slow startup (>2 min) | Cosmos emulator is heavyweight — first pull is ~2GB. Subsequent starts use cached image |
| `docker exec` hangs on `kafka-console-producer` | Ensure you pipe input with `echo '...' \|` — interactive mode hangs in scripts |
| AppHost crashes with port conflict | Another AppHost or docker-compose may be running — `docker ps` and kill conflicts |
