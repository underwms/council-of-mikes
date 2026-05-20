---
name: aspire-apphost-setup
description: "Use when adding .NET Aspire AppHost to an existing .NET solution for local development orchestration — setting up container-based infrastructure (Kafka, Temporal, Cosmos DB, Service Bus), configuring the AppHost project SDK, wiring service projects, forwarding environment variables, or troubleshooting Aspire build errors like ASPIRECOSMOSDB001"
---

# .NET Aspire AppHost Setup

Add an Aspire AppHost project to orchestrate local infrastructure (Kafka, Temporal, Cosmos DB, Service Bus) for .NET services. The AppHost replaces docker-compose with a programmatic C# model.

## When to Use

- Adding local development infrastructure to an existing .NET service
- Replacing docker-compose with Aspire orchestration
- Setting up container-based Kafka, Temporal, Cosmos DB, or Service Bus emulators
- Seeing `ASPIRECOSMOSDB001` or other Aspire preview warnings
- Need to forward configuration sections as environment variables to service projects

## Core Pattern

```
AppHost project (Aspire SDK)
  ├── AppHost.cs              → Entry point: DistributedApplication.CreateBuilder
  ├── AppHostSettings.cs      → Feature flags (UseKafkaEmulator, UseCosmosDbEmulator, etc.)
  ├── Extensions/
  │   ├── AppBuilderExtensions.cs  → Resource setup (Cosmos, Kafka, Temporal)
  │   └── AppHostExtensions.cs     → Config binding, env var forwarding
  └── appsettings.json        → Master config with AppHost section + service sections
```

## Quick Reference

| Component | Package | Notes |
|-----------|---------|-------|
| Aspire SDK | `Aspire.AppHost.Sdk/13.1.1` | Replaces `Microsoft.NET.Sdk` in `.csproj` |
| Cosmos DB | `Aspire.Hosting.Azure.CosmosDB` | Use `.RunAsPreviewEmulator()` + `<NoWarn>ASPIRECOSMOSDB001</NoWarn>` |
| Temporal | `InfinityFlow.Aspire.Temporal` | Community package, provides `AddTemporalServerContainer` |
| Kafka | Manual container setup | Use `cp-server:7.9.2` image with KRaft mode |
| Service Bus | `Aspire.Hosting.Azure.ServiceBus` | Use `.RunAsEmulator()` |

## Implementation Steps

### 1. Create AppHost Project

Create a new project directory alongside existing service projects:

```
src/
  YourService.Web/           ← existing service
  YourService.AppHost/       ← new AppHost project
```

**`.csproj`** — Use Aspire SDK, NOT `Microsoft.NET.Sdk`:

```xml
<Project Sdk="Aspire.AppHost.Sdk/13.1.1">

  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net10.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <IsAspireHost>true</IsAspireHost>
    <!-- Suppress Cosmos DB emulator preview warning -->
    <NoWarn>$(NoWarn);ASPIRECOSMOSDB001</NoWarn>
  </PropertyGroup>

  <ItemGroup>
    <!-- Reference your service project(s) -->
    <ProjectReference Include="..\YourService.Web\YourService.Web.csproj" />
  </ItemGroup>

  <ItemGroup>
    <!-- Aspire hosting packages -->
    <PackageReference Include="Aspire.Hosting.Azure.CosmosDB" />
    <PackageReference Include="InfinityFlow.Aspire.Temporal" />
    <!-- Add others as needed: Aspire.Hosting.Azure.ServiceBus -->
  </ItemGroup>

</Project>
```

If using centralized package management (`Directory.Packages.props`), add versions there:
```xml
<PackageVersion Include="Aspire.Hosting.Azure.CosmosDB" Version="13.1.1" />
<PackageVersion Include="InfinityFlow.Aspire.Temporal" Version="0.8.1" />
```

### 2. Create AppHostSettings

Strongly-typed feature flags controlling which emulators are enabled:

```csharp
public class AppHostSettings
{
    public bool UseTemporalEmulator { get; set; } = true;
    public bool UseCosmosDbEmulator { get; set; } = true;
    public bool UseKafkaEmulator { get; set; } = true;
    public bool UseKafkaEmulatorUi { get; set; } = true;
}
```

### 3. Create AppHost Entry Point

```csharp
public class AppHost
{
    public static async Task Main(string[] args)
    {
        var builder = DistributedApplication.CreateBuilder(args);

        // Bind config from appsettings.json
        var appHostSettings = builder.Configuration
            .GetSection("AppHost")
            .Get<AppHostSettings>() ?? new AppHostSettings();

        // Add your service project
        var service = builder
            .AddProject<Projects.YourService_Web>("YourService")
            .WithEnvironmentForwardedFrom(builder.Configuration.GetSection("shared"))
            .WithEnvironmentForwardedFrom(builder.Configuration.GetSection("yourservice"));

        // Conditionally add infrastructure emulators
        if (appHostSettings.UseTemporalEmulator)
        {
            var temporal = builder.AddTemporalServerContainer("temporal");
            service.WithTemporalReference(temporal, "shared:TemporalSettings:Clients:YourClient");
        }

        if (appHostSettings.UseCosmosDbEmulator)
        {
            var cosmosDb = builder.AddAzureCosmosDB("cosmos")
                .RunAsPreviewEmulator(config =>
                {
                    config.WithGatewayPort(10250);
                    config.WithDataExplorerPort(10251);
                });
            service.WithCosmosDbReference(cosmosDb, "shared:CosmosDbSettings");
        }

        if (appHostSettings.UseKafkaEmulator)
        {
            service.WithKafkaReference(builder, "shared:KafkaSettings");
        }

        builder.Build().Run();
    }
}
```

### 4. Create Extension Methods

**Environment variable forwarding** — flattens config sections to `__`-delimited env vars:

```csharp
public static class AppHostExtensions
{
    /// <summary>
    /// Forwards all keys from a configuration section as environment variables.
    /// Colons in key paths are replaced with double underscores.
    /// </summary>
    public static IResourceBuilder<ProjectResource> WithEnvironmentForwardedFrom(
        this IResourceBuilder<ProjectResource> project,
        IConfigurationSection section)
    {
        foreach (var child in section.GetChildren())
        {
            if (child.Value is not null)
            {
                var envKey = $"{section.Key}__{child.Path[(section.Path.Length + 1)..]}"
                    .ReplaceColonWithDoubleUnderScores();
                project = project.WithEnvironment(envKey, child.Value);
            }
        }
        return project;
    }

    public static string ReplaceColonWithDoubleUnderScores(this string input)
        => input.Replace(":", "__");
}
```

**Cosmos DB reference** — sets connection string and gateway mode:

```csharp
public static IResourceBuilder<ProjectResource> WithCosmosDbReference(
    this IResourceBuilder<ProjectResource> project,
    IResourceBuilder<AzureCosmosDBResource> cosmosDb,
    string configPrefix)
{
    return project
        .WithReference(cosmosDb)
        .WithEnvironment(ctx =>
        {
            var prefix = configPrefix.ReplaceColonWithDoubleUnderScores();
            ctx.EnvironmentVariables[$"{prefix}__CosmosGatewayMode"] = "true";
            // Clear managed identity — emulator uses key-based auth
            ctx.EnvironmentVariables["AZURE_CLIENT_ID"] = "";
        });
}
```

**Temporal reference** — overrides `ClientTargetHost` for emulator:

```csharp
public static IResourceBuilder<ProjectResource> WithTemporalReference(
    this IResourceBuilder<ProjectResource> project,
    IResourceBuilder<TemporalServerResource> temporal,
    params string[] clientConfigPaths)
{
    return project
        .WithReference(temporal)
        .WithEnvironment(ctx =>
        {
            foreach (var path in clientConfigPaths)
            {
                var key = $"{path}:ClientTargetHost".ReplaceColonWithDoubleUnderScores();
                ctx.EnvironmentVariables[key] = temporal.Resource.PrimaryEndpoint;
            }
        });
}
```

**Kafka reference** — creates broker, schema registry, and control center:

```csharp
public static IResourceBuilder<ProjectResource> WithKafkaReference(
    this IResourceBuilder<ProjectResource> project,
    IDistributedApplicationBuilder builder,
    string configPath,
    bool withUi = true)
{
    var kafka = builder.AddContainer("kafka", "confluentinc/cp-server", "7.9.2")
        .WithEndpoint(port: 9092, targetPort: 9092, name: "external", scheme: "tcp")
        .WithEndpoint(port: 29092, targetPort: 29092, name: "internal", scheme: "tcp")
        .WithEnvironment("KAFKA_NODE_ID", "1")
        .WithEnvironment("KAFKA_PROCESS_ROLES", "broker,controller")
        .WithEnvironment("KAFKA_CONTROLLER_QUORUM_VOTERS", "1@kafka:29093")
        .WithEnvironment("KAFKA_LISTENERS",
            "PLAINTEXT://0.0.0.0:29092,CONTROLLER://0.0.0.0:29093,EXTERNAL_SASL://0.0.0.0:9092")
        .WithEnvironment("KAFKA_ADVERTISED_LISTENERS",
            "PLAINTEXT://kafka:29092,EXTERNAL_SASL://localhost:9092")
        .WithEnvironment("KAFKA_LISTENER_SECURITY_PROTOCOL_MAP",
            "CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,EXTERNAL_SASL:SASL_PLAINTEXT")
        .WithEnvironment("KAFKA_CONTROLLER_LISTENER_NAMES", "CONTROLLER")
        .WithEnvironment("KAFKA_INTER_BROKER_LISTENER_NAME", "PLAINTEXT")
        .WithEnvironment("CLUSTER_ID", "MkU3OEVBNTcwNTJENDM2Qk");

    var schemaRegistry = builder.AddContainer("schema-registry", "confluentinc/cp-schema-registry", "7.9.2")
        .WithEndpoint(port: 8081, targetPort: 8081, name: "http", scheme: "http")
        .WithEnvironment("SCHEMA_REGISTRY_HOST_NAME", "schema-registry")
        .WithEnvironment("SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS", "kafka:29092")
        .WaitFor(kafka);

    if (withUi)
    {
        builder.AddContainer("control-center", "confluentinc/cp-enterprise-control-center", "7.9.2")
            .WithEndpoint(port: 9021, targetPort: 9021, name: "http", scheme: "http")
            .WithEnvironment("CONTROL_CENTER_BOOTSTRAP_SERVERS", "kafka:29092")
            .WithEnvironment("CONTROL_CENTER_SCHEMA_REGISTRY_URL", "http://schema-registry:8081")
            .WithEnvironment("CONTROL_CENTER_REPLICATION_FACTOR", "1")
            .WaitFor(kafka).WaitFor(schemaRegistry);
    }

    var prefix = configPath.ReplaceColonWithDoubleUnderScores();
    return project.WithEnvironment(ctx =>
    {
        ctx.EnvironmentVariables[$"{prefix}__BootstrapServerEndpoint"] = "localhost:9092";
        ctx.EnvironmentVariables[$"{prefix}__SchemaRegistryUrl"] = "http://localhost:8081";
    });
}
```

### 5. Configure appsettings.json

The AppHost's `appsettings.json` is the single source of truth for local development:

```json
{
  "AppHost": {
    "UseTemporalEmulator": true,
    "UseCosmosDbEmulator": true,
    "UseKafkaEmulator": true,
    "UseKafkaEmulatorUi": true
  },
  "shared": {
    "TemporalSettings": {
      "Clients": {
        "YourClient": {
          "ClientTargetHost": "localhost:7233",
          "Namespace": "default"
        }
      }
    },
    "KafkaSettings": {
      "BootstrapServerEndpoint": "localhost:9092",
      "SchemaRegistryUrl": "http://localhost:8081"
    },
    "CosmosDbSettings": {
      "ConnectionString": "",
      "DatabaseName": "your-database"
    }
  },
  "yourservice": {
    // Service-specific settings forwarded as env vars
  }
}
```

### 6. Link Development Config Files (Optional)

If your service projects have their own `appsettings.Development.json`, link them in the AppHost `.csproj`:

```xml
<ItemGroup>
  <Content Include="..\YourService.Web\appsettings.Development.json"
           Link="appsettings.YourService.json"
           CopyToOutputDirectory="PreserveNewest" />
</ItemGroup>
```

Then in `AppHost.cs`, add them to the configuration builder:

```csharp
builder.Configuration.AddJsonFile("appsettings.YourService.json", optional: true);
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using `Microsoft.NET.Sdk` in AppHost `.csproj` | Must use `Aspire.AppHost.Sdk/13.1.1` |
| `ASPIRECOSMOSDB001` build warnings | Add `<NoWarn>$(NoWarn);ASPIRECOSMOSDB001</NoWarn>` |
| Kafka consumers can't connect inside container | Use PLAINTEXT listener on `kafka:29092` (container name), not `localhost:9092` |
| Cosmos emulator SSL errors | See `aspire-local-testing` skill for cert setup |
| Hardcoding connection strings | Use `WithEnvironmentForwardedFrom` to flow config as env vars |
| Missing `<IsAspireHost>true</IsAspireHost>` | Required for Aspire tooling and dashboard |
| Adding AppHost to main solution | Consider keeping it separate — it's a dev-only orchestrator |
| Not using `WaitFor()` on dependent containers | Schema Registry and Control Center must `WaitFor(kafka)` |

## ServiceDefaults (Optional)

For services that benefit from Aspire service discovery, resilience, and OpenTelemetry integration, add a ServiceDefaults shared library:

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <IsAspireSharedProject>true</IsAspireSharedProject>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.Extensions.Http.Resilience" />
    <PackageReference Include="Microsoft.Extensions.ServiceDiscovery" />
  </ItemGroup>
</Project>
```

Reference it from service projects that need distributed app features. Not required for basic AppHost orchestration.
