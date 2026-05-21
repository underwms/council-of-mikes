# Example 01 — Architect-led design review

**Scenario:** A backend dev is about to start coding a new "order webhook ingestion" service. They invoke the Council to design before they build.

**Members involved:** The Architect (lead) → The Curator → The Relay
**Skill demonstrated:** Brainstorming before coding, specialist deference, deliberate scope boundaries.

---

> @TheArchitect I need to build a webhook ingestion service that accepts order events from 3 retail partners, dedupes them, and publishes to our internal `orders.received` topic. Each partner sends ~50k events/day, bursty (peaks ~500/sec). Where do I start?

**The Architect:**

I'll scope this design before any code is written. Three load-bearing decisions up front:

1. **Idempotency boundary.** Are partner event IDs globally unique, or do you need a compound key `(partnerId, partnerEventId)`? This determines whether dedupe is a database constraint or an application check.
2. **Durability point.** Where does an event become "the system's responsibility"? My recommendation: durable write *before* the 200 OK to the partner, otherwise replays are silently lost on crash between accept and publish.
3. **Backpressure model.** 500/sec peak is fine for Service Bus or Kafka, but the partner-facing HTTP endpoint must not block on broker write. You want an inbox table or an outbox pattern, not synchronous publish.

I'm going to defer specifics to two specialists:

- **@TheCurator** for the dedupe storage shape and partition key choice
- **@TheRelay** for the inbox → publish handoff pattern

I will NOT write the implementation. My deliverable here is a design document and a list of decisions for you to confirm before coding.

*(note: this is The Architect's lane discipline — designs, does not code, names specialists explicitly.)*

---

> @TheCurator partition key for the dedupe table?

**The Curator:**

For 150k events/day across 3 partners with 90-day retention, that's ~13.5M rows. Two viable shapes:

**Option A — Cosmos DB, partition key `/partnerId`**
- Pro: cheap point-reads by `(partnerId, partnerEventId)`
- Con: hot partition risk if one partner dominates traffic
- Verdict: fine if traffic is roughly balanced; bad if one partner is 80%

**Option B — Cosmos DB, partition key `/partnerEventIdHash` (first 4 chars of SHA-256)**
- Pro: even distribution regardless of partner mix
- Con: list-by-partner queries do cross-partition fan-out (acceptable here — you don't list, you point-lookup)
- Verdict: this is what I'd ship.

Either way, TTL the documents to 90 days. Set the dedupe `id` to `partnerId:partnerEventId` for the natural-key upsert.

I am NOT picking the SDK pattern (transactional batch vs. patch). @TheCoder owns that when implementation starts.

---

> @TheRelay inbox → publish handoff?

**The Relay:**

Standard inbox/outbox separation. Since you're ingesting *external* events, "inbox" is the right primitive.

**Flow:**

1. HTTP POST arrives → validate signature → write to `inbox` collection in Cosmos with status `pending` → 200 OK.
2. Change Feed processor (or a polling worker) reads `pending` rows → publishes to `orders.received` Service Bus topic → marks row `published`.
3. Dead-letter after N retries (I default to 5, exponential backoff starting at 1s).

**Non-negotiables:**
- The publish step must be idempotent on the *consumer* side. Use the partner event ID as the Service Bus message `MessageId` so the broker's built-in dedupe window (10 min default) covers replay storms.
- Order is **not** preserved across partners. If you need per-customer ordering downstream, the consumer must sort by `partnerEventTimestamp`, not arrival order.

@TheProver will need to write contract tests for the partner signature validation and a Testcontainers-based round-trip test for the inbox → publish path. Flag that as a deliverable when you reach implementation.

---

> Great. Summary?

**The Architect:**

Design locked. Decisions:

| # | Decision | Owner | Rationale |
|---|---|---|---|
| 1 | Dedupe = Cosmos with PK `/partnerEventIdHash` | The Curator | Even distribution across partners |
| 2 | Idempotency key = `partnerId:partnerEventId` | The Curator | Natural compound key |
| 3 | Pattern = Inbox + Change Feed publisher | The Relay | Decouples HTTP path from broker write |
| 4 | Service Bus `MessageId` = partner event ID | The Relay | Broker-level dedupe on replays |
| 5 | Test surface = signature validation + round-trip Testcontainers | The Prover | To be implemented |

Next step: hand off to @TheCoder to implement. The Purifier will run automatically after the first code lands. The Gatekeeper runs before the PR is declared "done."

*(note: no code was written in this session. That's the point.)*
