import { DatabaseSync } from "node:sqlite";
import { createHandler } from "../server/main.ts";
import { readObservation } from "../src/observations.ts";

Deno.test("observations backend: bounded retrieval preserves privacy and local access", async () => {
  const root = await Deno.makeTempDir({ dir: "tests" });
  try {
    await Deno.mkdir(`${root}/diagnostics`);
    const db = new DatabaseSync(`${root}/observability.sqlite`);
    db.exec(
      "CREATE TABLE observation_meta(version INTEGER); INSERT INTO observation_meta VALUES (1); CREATE TABLE observation_sessions(generation INTEGER,run_id TEXT,session_id TEXT); CREATE TABLE observation_events(position INTEGER,run_id TEXT,session_id TEXT,source_seq INTEGER,event_id TEXT,event TEXT,payload TEXT)",
    );
    db.prepare("INSERT INTO observation_sessions VALUES (1,'run','session')")
      .run();
    const insert = db.prepare(
      "INSERT INTO observation_events VALUES (?,'run','session',?,?,'call_failed',?)",
    );
    for (let i = 1; i <= 3; i++) {
      insert.run(
        i,
        i,
        "a".repeat(64),
        JSON.stringify({
          timestamp: "2026-10-25T18:00:00+00:00",
          event: "call_failed",
          stage: "model",
          call: i,
          code: "FINAL_REVIEW_NON_TEXT_UNSUPPORTED",
          prompt: "PRIVATE",
          comparison: {
            accepted_plan_sha256: "b".repeat(64),
            engine_graph_sha256: "c".repeat(64),
            raw: "PRIVATE",
          },
          accounting: {
            usage: { input_tokens: 10 },
            duration_seconds: i,
            raw: "PRIVATE",
          },
        }),
      );
    }
    db.close();
    const handler = createHandler({
      runId: "run",
      diagnosticsDir: `${root}/diagnostics`,
      distDir: root,
    });
    const transport: typeof fetch = (input, options) =>
      handler(
        new Request(new URL(String(input), "http://127.0.0.1"), {
          signal: options?.signal ?? undefined,
        }),
      );
    const decodedSummary = await readObservation(
      "run",
      "summary",
      0,
      "reported_model",
      new AbortController().signal,
      transport,
    );
    if (
      decodedSummary.usage.reported_input_tokens !== 30 ||
      decodedSummary.usage.reported_total_tokens !== null ||
      decodedSummary.groups[0].value !== null
    ) {
      throw new Error("Browser decoder disagrees with real SQLite summary");
    }
    const decodedCalls = await readObservation(
      "run",
      "calls",
      0,
      undefined,
      new AbortController().signal,
      transport,
    );
    if (
      decodedCalls.items.length !== 3 ||
      decodedCalls.items[0].code !== "FINAL_REVIEW_NON_TEXT_UNSUPPORTED" ||
      decodedCalls.items[0].comparison?.accepted_plan_sha256 !==
        "b".repeat(64) ||
      JSON.stringify(decodedCalls).includes("PRIVATE")
    ) {
      throw new Error(
        "Browser decoder loses safe provenance or leaks private data",
      );
    }
    const response = await handler(
      new Request("http://127.0.0.1/api/v1/runs/run/calls?limit=2"),
    );
    if (response.status !== 200) {
      throw new Error(`Expected 200: ${response.status}`);
    }
    const page = await response.json();
    if (
      page.items.length !== 2 || page.next_cursor !== 2 ||
      JSON.stringify(page).includes("PRIVATE")
    ) throw new Error("Invalid private page");
    const summary = await (await handler(
      new Request("http://127.0.0.1/api/v1/runs/run/summary"),
    )).json();
    if (
      summary.calls.count !== 3 || summary.usage.reported_input_tokens !== 30 ||
      summary.wall_time_seconds !== null
    ) throw new Error("Invalid summary");
    if (summary.comparison.accepted_plan_sha256 !== "b".repeat(64)) {
      throw new Error("Comparison identity missing");
    }
    if (summary.usage.reported_total_tokens !== null) {
      throw new Error("Missing provider totals became zero");
    }
    const grouped = await (await handler(
      new Request(
        "http://127.0.0.1/api/v1/runs/run/summary?group_by=requested_model",
      ),
    )).json();
    if (grouped.groups.length !== 1 || grouped.groups[0].value !== null) {
      throw new Error("Unreported model was fabricated");
    }
    if (
      (await handler(
        new Request("http://127.0.0.1/api/v1/runs/run/summary?group_by=prompt"),
      )).status !== 400
    ) throw new Error("Unsupported grouping accepted");
    if (
      (await handler(
        new Request("http://127.0.0.1/api/v1/runs/run/events?limit=201"),
      )).status !== 400
    ) throw new Error("Unbounded query accepted");
    if (
      (await handler(new Request("http://127.0.0.1/api/v1/runs/other/summary")))
        .status !== 404
    ) throw new Error("Cross-run access accepted");
    if (
      (await handler(
        new Request("http://127.0.0.1/api/v1/runs/run/summary", {
          headers: { origin: "http://evil.example" },
        }),
      )).status !== 403
    ) throw new Error("Cross-origin access accepted");
  } finally {
    await Deno.remove(root, { recursive: true });
  }
});
