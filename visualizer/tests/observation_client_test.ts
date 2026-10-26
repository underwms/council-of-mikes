import {
  causalOrder,
  decodePage,
  decodeSummary,
  mergePage,
  readObservation,
} from "../src/observations.ts";

function assert(value: unknown, message: string): asserts value {
  if (!value) throw new Error(message);
}
function rejects(action: () => unknown, message: string) {
  try {
    action();
  } catch {
    return;
  }
  throw new Error(message);
}
const summary = {
  version: 1,
  run_id: "run",
  coverage: "prospective_events_only",
  liveness: "unknown",
  current: {
    state: "waiting_for_human",
    message: "Waiting for explicit human input.",
    timestamp: "2026-10-25T12:00:00Z",
  },
  usage: {
    reported_input_tokens: 12,
    reported_output_tokens: null,
    reported_total_tokens: null,
    measured_attempts: 1,
    missing_attempts: 2,
    partial_attempts: 1,
    field_attempt_counts: { input_tokens: 1 },
  },
  calls: { count: 3, median_seconds: 4.5, duration_population: 2 },
  comparison: {
    distribution_version: "0.2.43",
    engine_graph_sha256: "a".repeat(64),
    roles: {
      coder: {
        requested_model: "requested",
        provider: "codex",
        configured_timeout_seconds: 90,
      },
    },
  },
  wall_time_seconds: null,
  unclassified_gaps: true,
  history_capped: false,
};
const item = (position: number, generation = 1, seq = position) => ({
  position,
  session_id: `session-${generation}`,
  session_generation: generation,
  source_seq: seq,
  event_id: "a".repeat(64),
  event: "call_failed",
  stage: "worker",
  timestamp: "2026-10-25T12:00:00Z",
  accounting: {
    requested_model: "requested",
    duration_seconds: 2,
    usage: { input_tokens: 12 },
    prompt: "PRIVATE",
  },
  prompt: "PRIVATE",
});

Deno.test("observation client: summary retains unknown measurements and identity", () => {
  const decoded = decodeSummary(summary, "run");
  assert(decoded.current?.state === "waiting_for_human", "Human wait missing");
  assert(
    decoded.usage.reported_total_tokens === null,
    "Missing tokens became zero",
  );
  assert(decoded.wall_time_seconds === null, "Invented wall time");
  assert(
    decoded.comparison?.distribution_version === "0.2.43",
    "Installed identity missing",
  );
  assert(
    decoded.comparison?.roles.coder.requested_model === "requested",
    "Requested model missing",
  );
  assert(
    decoded.usage.field_attempt_counts.input_tokens === 1,
    "Metric population missing",
  );
});

Deno.test("observation client: malformed, cross-run and unsupported summaries are bounded", () => {
  rejects(
    () => decodeSummary({ ...summary, run_id: "other" }, "run"),
    "Accepted wrong run",
  );
  rejects(
    () => decodeSummary({ ...summary, version: 2 }, "run"),
    "Accepted unknown version",
  );
  rejects(() => decodeSummary(null, "run"), "Accepted null");
  assert(
    decodeSummary({ version: 1, status: "unsupported_schema" }, "run")
      .status === "unsupported_schema",
    "Schema status lost",
  );
  assert(
    decodeSummary({ version: 1, status: "unavailable" }, "run").current ===
      null,
    "Fabricated unavailable state",
  );
  const decoded = decodeSummary({
    ...summary,
    usage: { reported_total_tokens: -1, measured_attempts: Infinity },
  }, "run");
  assert(
    decoded.usage.reported_total_tokens === null &&
      decoded.usage.measured_attempts === null,
    "Invalid measurement survived",
  );
});

Deno.test("observation client: page projection drops private fields and preserves provenance", () => {
  const page = decodePage(
    { version: 1, items: [item(1)], next_cursor: 1 },
    "calls",
    0,
  );
  assert(page.items[0].session_generation === 1, "Missing causal identity");
  assert(
    page.items[0].accounting?.returned_model === null,
    "Requested model promoted to effective model",
  );
  assert(
    !JSON.stringify(page).includes("PRIVATE"),
    "Private payload escaped allowlist",
  );
  assert(page.next_cursor === 1, "Lost ingestion cursor");
});

Deno.test("observation client: page limits and cursor progression are enforced", () => {
  rejects(
    () =>
      decodePage({ version: 1, items: [item(2)], next_cursor: 1 }, "events", 0),
    "Accepted item beyond cursor",
  );
  rejects(
    () =>
      decodePage({ version: 1, items: [item(1)], next_cursor: 1 }, "events", 1),
    "Accepted repeated item",
  );
  rejects(
    () =>
      decodePage(
        {
          version: 1,
          items: Array.from({ length: 201 }, (_, i) => item(i + 1)),
          next_cursor: 201,
        },
        "events",
        0,
      ),
    "Accepted unbounded page",
  );
  rejects(
    () => decodePage({ version: 1, items: [], next_cursor: -1 }, "events", 0),
    "Accepted invalid cursor",
  );
  rejects(
    () =>
      decodePage(
        { version: 1, items: [item(2), item(1)], next_cursor: 2 },
        "events",
        0,
      ),
    "Accepted unordered ingestion positions",
  );
  assert(
    decodePage({ version: 1, items: [], next_cursor: 4 }, "events", 2)
      .next_cursor === 4,
    "Filtered page cannot advance",
  );
});

Deno.test("observation client: delayed sessions sort causally without changing cursor", () => {
  const first = decodePage(
    { version: 1, items: [item(1, 2, 1)], next_cursor: 1 },
    "events",
    0,
  );
  const later = decodePage(
    { version: 1, items: [item(2, 1, 9)], next_cursor: 2 },
    "events",
    1,
  );
  const merged = mergePage(first, later);
  assert(merged.next_cursor === 2, "Causal sorting changed ingestion cursor");
  assert(
    causalOrder(merged.items)[0].position === 2,
    "Delayed event not inserted causally",
  );
  assert(
    mergePage(merged, later).items.length === 2,
    "Redelivery duplicated event",
  );
});

Deno.test("observation client: session pages and verification measurements are typed", () => {
  const sessions = decodePage(
    {
      version: 1,
      items: [{ position: 1, session_id: "session" }],
      next_cursor: 1,
    },
    "sessions",
    0,
  );
  assert(
    sessions.items[0].session_id === "session",
    "Session identity missing",
  );
  const commands = decodePage(
    {
      version: 1,
      items: [{
        ...item(1),
        event: "verification_finished",
        measurement: {
          execution_id: "b".repeat(64),
          command_sha256: "c".repeat(64),
          duration_seconds: 0,
          completion: "completed",
          started_utc: "2026-10-25T12:00:00Z",
          ended_utc: "2026-10-25T12:00:00Z",
        },
        functional_complete: true,
        pr_ready: false,
      }],
      next_cursor: 1,
    },
    "commands",
    0,
  );
  assert(
    commands.items[0].measurement?.duration_seconds === 0,
    "Measured zero lost",
  );
  assert(
    commands.items[0].functional_complete === true &&
      commands.items[0].pr_ready === false,
    "Delivery fields merged",
  );
});

Deno.test("observation client: fetch uses selected run and bounds HTTP response", async () => {
  let observed = "";
  const fetcher: typeof fetch = (input, init) => {
    observed = String(input);
    assert(
      init?.cache === "no-store" && init.signal,
      "Missing cache/cancellation contract",
    );
    return Promise.resolve(Response.json(summary));
  };
  await readObservation(
    "run",
    "summary",
    0,
    "role",
    new AbortController().signal,
    fetcher,
  );
  assert(
    observed === "/api/v1/runs/run/summary?group_by=role",
    "Incorrect selected-run URL",
  );
  for (
    const response of [
      new Response("bad", { status: 503 }),
      new Response("x".repeat(1024 * 1024 + 1)),
    ]
  ) {
    let failed = false;
    try {
      await readObservation(
        "run",
        "summary",
        0,
        undefined,
        new AbortController().signal,
        () => Promise.resolve(response),
      );
    } catch {
      failed = true;
    }
    assert(failed, "Accepted failed or oversized response");
  }
});

Deno.test("observation client: aborted reads and invalid identifiers do not publish observations", async () => {
  const controller = new AbortController();
  controller.abort();
  let called = false;
  const fetcher: typeof fetch = () => {
    called = true;
    return Promise.resolve(Response.json(summary));
  };
  for (const run of ["../private", "run"]) {
    let failed = false;
    try {
      await readObservation(
        run,
        "summary",
        0,
        undefined,
        controller.signal,
        fetcher,
      );
    } catch {
      failed = true;
    }
    assert(failed, "Invalid/aborted request accepted");
  }
  assert(!called, "Invalid request reached transport");
});

Deno.test("observation client: bounded windows and unavailable pages cannot invent retained facts", () => {
  const first = decodePage(
    { version: 1, items: [item(1)], next_cursor: 1 },
    "events",
    0,
  );
  let combined = first;
  for (let after = 1; after < 1001; after += 100) {
    const items = Array.from({ length: 100 }, (_, i) => item(after + i + 1));
    combined = mergePage(
      combined,
      decodePage(
        { version: 1, items, next_cursor: after + 100 },
        "events",
        after,
      ),
    );
  }
  assert(
    combined.items.length === 1000 && combined.items[0].position === 2,
    "Retained window unbounded",
  );
  const unavailable = decodePage(
    { version: 1, status: "unavailable" },
    "events",
    1001,
  );
  assert(
    mergePage(combined, unavailable).items.length === 0,
    "Unavailable store retained current claims",
  );
  rejects(
    () =>
      decodePage({ version: 1, items: [item(0)], next_cursor: 0 }, "events", 0),
    "Accepted invalid position",
  );
  rejects(
    () => decodeSummary({ ...summary, status: "unexpected" }, "run"),
    "Accepted arbitrary status",
  );
  rejects(
    () => decodeSummary({ ...summary, groups: Array(65).fill({}) }, "run"),
    "Accepted excess groups",
  );
  const compared = decodeSummary({
    ...summary,
    comparison: {
      policy: { recovery: 2, unknown: 3, governance: -1 },
      roles: { coder: { provider: "codex" } },
    },
  }, "run");
  assert(
    JSON.stringify(compared.comparison?.policy) === '{"recovery":2}',
    "Invalid policy fields survived",
  );
});
