import { DatabaseSync } from "node:sqlite";
import { createHandler } from "../server/main.ts";
import { readNarrations } from "../server/narrations.ts";
import {
  decodeNarrations,
  eventNodeBlurb,
  latestNodeNarration,
} from "../src/narrations.ts";
import { parseRecording } from "../src/contracts.ts";
import { projectAt } from "../src/reducer.ts";

Deno.test("narration: SQLite projection exposes linked narration independently of event pagination", async () => {
  const dir = await Deno.makeTempDir({ dir: "tests" });
  try {
    const path = `${dir}/observability.sqlite`;
    if (readNarrations(path, "run").status !== "unavailable") {
      throw new Error("Missing storage must be explicit");
    }
    const db = new DatabaseSync(path);
    db.exec(
      "CREATE TABLE node_narration_meta(version INTEGER); INSERT INTO node_narration_meta VALUES(1); CREATE TABLE observation_sessions(run_id TEXT,session_id TEXT,generation INTEGER); INSERT INTO observation_sessions VALUES('run','session',1); CREATE TABLE observation_events(position INTEGER,run_id TEXT,session_id TEXT,source_seq INTEGER,event_id TEXT,event TEXT,payload TEXT); CREATE TABLE node_narrations(position INTEGER,source_event_id TEXT,run_id TEXT,session_id TEXT,stage TEXT,visit_id TEXT,source_position INTEGER,message TEXT,status TEXT,method TEXT,generated_at TEXT,accounting TEXT)",
    );
    const stamp = "2026-10-26T16:00:00+00:00";
    db.prepare(
      "INSERT INTO observation_events VALUES (1,'run','session',1,?,'node_started',?)",
    ).run(
      "a".repeat(64),
      JSON.stringify({ stage: "worker", timestamp: stamp }),
    );
    db.prepare(
      "INSERT INTO node_narrations VALUES (1,?,'run','session','worker',?,1,'Implementing the readiness fixture.','succeeded','model',?,?)",
    ).run(
      "a".repeat(64),
      "a".repeat(64),
      stamp,
      JSON.stringify({
        requested_model: "model",
        prompt: "PRIVATE",
        usage: { input_tokens: 10 },
      }),
    );
    db.close();
    const page = readNarrations(path, "run");
    if (JSON.stringify(page).includes("PRIVATE")) {
      throw new Error("Raw accounting escaped");
    }
    const handler = createHandler({
      runId: "run",
      diagnosticsDir: `${dir}/diagnostics`,
      distDir: dir,
    });
    const response = await handler(
      new Request("http://127.0.0.1/api/v1/runs/run/narrations"),
    );
    if (
      response.status !== 200 ||
      decodeNarrations(await response.json(), 0).items.length !== 1
    ) throw new Error("Read-only narration HTTP route failed");
    if (
      (await handler(
        new Request("http://127.0.0.1/api/v1/runs/run/narrations", {
          method: "POST",
        }),
      )).status !== 405
    ) throw new Error("Narration API permitted a write");
    if (
      (await handler(
        new Request("http://127.0.0.1/api/v1/runs/other/narrations"),
      )).status !== 404
    ) throw new Error("Narration API crossed run selection");
    const decoded = decodeNarrations(page, 0);
    if (decoded.items.length !== 1 || decoded.items[0].stage !== "worker") {
      throw new Error("Narration missing from projection");
    }
    if (decodeNarrations(readNarrations(path, "run", 1), 1).items.length) {
      throw new Error("Cursor replayed narration");
    }
    const events = parseRecording(
      JSON.stringify({
        run_id: "run",
        timestamp: stamp,
        event: "node_started",
        stage: "worker",
        elapsed_seconds: 0,
      }),
    );
    const state = projectAt(events, 1);
    if (!latestNodeNarration("worker", state, decoded.items)) {
      throw new Error("Originating visit did not receive narration");
    }
    if (latestNodeNarration("prover", state, decoded.items)) {
      throw new Error("Narration attached to wrong node");
    }
    const current = decoded.items[0];
    const newer = {
      ...current,
      position: 2,
      source_position: 4,
      message: "The coding turn returned; verification is pending.",
    };
    if (
      latestNodeNarration("worker", state, [newer, current])
        ?.source_position !== 4
    ) throw new Error("Delayed narration regressed source order");
    if (
      latestNodeNarration("worker", state, [{
        ...current,
        source_timestamp: "2026-10-26T16:05:00+00:00",
      }])
    ) throw new Error("Future activity escaped observation position");
    const later = parseRecording(
      [events[0].payload, {
        ...events[0].payload,
        timestamp: "2026-10-26T16:01:00+00:00",
        elapsed_seconds: 60,
      }].map((e) => JSON.stringify(e)).join("\n"),
    );
    if (latestNodeNarration("worker", projectAt(later, 2), decoded.items)) {
      throw new Error("Previous visit bled into new visit");
    }
  } finally {
    await Deno.remove(dir, { recursive: true });
  }
});

Deno.test("narration: fallback distinguishes running, returned, failed and waiting without claiming success", () => {
  const stamp = "2026-10-26T16:00:00+00:00";
  const events = parseRecording(
    [
      { event: "node_started", stage: "worker" },
      { event: "call_started", stage: "model", call: 1 },
      { event: "call_succeeded", stage: "model", call: 1 },
      { event: "node_failed", stage: "worker" },
      { event: "node_started", stage: "requirements_gate" },
      { event: "approval_waiting", stage: "requirements_gate" },
    ].map((event, i) =>
      JSON.stringify({
        run_id: "run",
        timestamp: stamp,
        elapsed_seconds: i,
        ...event,
      })
    ).join("\n"),
  );
  if (
    !eventNodeBlurb("worker", projectAt(events, 2)).includes(
      "Verification is still required",
    )
  ) throw new Error("Running fallback invented completion");
  if (
    !eventNodeBlurb("worker", projectAt(events, 3)).includes(
      "not yet reported completion",
    )
  ) throw new Error("A returned call is not verified work");
  if (
    !eventNodeBlurb("worker", projectAt(events, 4)).includes("error stopped")
  ) throw new Error("Failure must remain explicit");
  if (
    !eventNodeBlurb("requirements_gate", projectAt(events, 6)).includes(
      "Waiting for a decision",
    )
  ) throw new Error("Waiting must remain explicit");
});
