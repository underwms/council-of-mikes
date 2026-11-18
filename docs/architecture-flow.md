# Native Council architecture

```mermaid
flowchart TD
    Repo[Portable repository] --> Setup[Native setup and source verification]
    Setup --> Root[Installed user Council]
    Root --> Skills[Canonical skill packages]
    Setup --> Pointers[Native profile pointers and hooks]
    Pointers --> Client[Native coding client]
    Skills --> Client
    Client --> Work[Authorized repository work]
    Client --> Checks[Tests and source review]
    Pointers --> Context[Bounded task context]
    Context --> Client
```

The client executes work through its own tools. Council instructions select relevant roles and workflows. Native subagents are optional and need bounded assignments. A role name can also mean guidance applied inline.

Task history and accepted knowledge have separate lifecycles. Startup context is historical data, not authorization. Knowledge publication requires its own explicit decision. The source includes no separate graph executor or background model service.
