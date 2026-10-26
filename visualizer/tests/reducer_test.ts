import { parseRecording } from "../src/contracts.ts";
import { initialRunState, projectAt } from "../src/reducer.ts";
import { nodeIsAnimating } from "../src/graphProgress.ts";

function equal(actual: unknown, expected: unknown, message: string): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(
      `${message}: ${JSON.stringify(actual)} != ${JSON.stringify(expected)}`,
    );
  }
}

Deno.test("reducer: real excerpt leaves reviewer call open and outcome unknown", async () => {
  const text = await Deno.readTextFile("tests/fixtures/sample-events.jsonl");
  const events = parseRecording(text);
  equal(events.length, 37, "event count");
  const state = projectAt(events, events.length);
  equal(state.activeNode, "plan_review", "active node");
  equal(
    state.visits.find((visit) => visit.nodeId === "architect")?.status,
    "finished",
    "architect status",
  );
  equal(state.visits.at(-1)?.calls.at(-1)?.status, "running", "reviewer call");
  equal(state.taskStatus, "unknown", "task status");
  equal(
    state.visits.find((visit) => visit.nodeId === "architect")?.inspectionRound,
    10,
    "inspection rounds",
  );
});

Deno.test("reducer: requirements waiting and delivery facts follow replay position", () => {
  const base = {
    run_id: "run",
    timestamp: "2026-10-25T12:00:00Z",
    elapsed_seconds: 0,
  };
  const events = parseRecording(
    [
      { event: "run_started", stage: "runtime" },
      { event: "node_started", stage: "requirements_gate" },
      { event: "approval_waiting", stage: "requirements_gate" },
      {
        event: "delivery_state",
        stage: "final_review",
        functional_complete: true,
        pr_ready: false,
      },
    ].map((event) => JSON.stringify({ ...base, ...event })).join("\n"),
  );
  const waiting = projectAt(events, 3);
  equal(waiting.visits.at(-1)?.status, "waiting", "Human approval waits");
  equal(
    nodeIsAnimating("requirements_gate", waiting, {
      mode: "live",
      atEnd: true,
      connected: true,
    }),
    false,
    "Waiting never animates",
  );
  equal(waiting.functionalComplete, null, "Future completion not visible");
  const delivered = projectAt(events, 4);
  equal(delivered.functionalComplete, true, "Reported functionality");
  equal(delivered.prReady, false, "PR readiness remains separate");
  equal(
    projectAt(events, 2).functionalComplete,
    null,
    "Rewind clears future facts",
  );
});

Deno.test("reducer: a new delivery boundary clears obsolete readiness", () => {
  const base = {
    run_id: "run",
    timestamp: "2026-10-25T12:00:00Z",
    elapsed_seconds: 0,
  };
  const events = parseRecording(
    [
      {
        event: "delivery_state",
        stage: "final_review",
        functional_complete: true,
        pr_ready: true,
      },
      { event: "node_started", stage: "requirements_reopen" },
      {
        event: "delivery_state",
        stage: "requirements_reopen",
        functional_complete: null,
        pr_ready: null,
      },
      { event: "planning_blocked", stage: "requirements_reopen" },
    ].map((event) => JSON.stringify({ ...base, ...event })).join("\n"),
  );
  const reopened = projectAt(events, 4);
  equal(reopened.functionalComplete, null, "Reopened functionality unknown");
  equal(
    reopened.prReady,
    null,
    "Old readiness cannot cross requirements boundary",
  );
  equal(
    reopened.visits.at(-1)?.status,
    "waiting",
    "Blocked planning awaits human",
  );
});

Deno.test("reducer: selection is independent of execution position", async () => {
  const text = await Deno.readTextFile("tests/fixtures/sample-events.jsonl");
  const events = parseRecording(text);
  const state = projectAt(events, events.length);
  equal(state.activeNode, "plan_review", "active node");
  equal(
    state.visits.filter((visit) => visit.nodeId === "architect").length,
    1,
    "architect visit",
  );
});

Deno.test("reducer: run_finished without task_status does not invent success", () => {
  const base = {
    run_id: "run",
    timestamp: "2026-01-01T00:00:00Z",
    elapsed_seconds: 0,
  };
  const events = parseRecording([
    JSON.stringify({ ...base, event: "run_started", stage: "runtime" }),
    JSON.stringify({
      ...base,
      event: "run_finished",
      stage: "runtime",
      elapsed_seconds: 1,
    }),
  ].join("\n"));
  const state = projectAt(events, events.length);
  equal(state.taskStatus, "unknown", "task status");
  equal(state.segmentOpen, false, "segment closed");
});

Deno.test("reducer: repeated visits and resume append order survive elapsed reset", () => {
  const base = { run_id: "run", timestamp: "2026-01-01T00:00:00Z" };
  const lines = [
    { event: "run_started", stage: "runtime", elapsed_seconds: 0 },
    { event: "node_started", stage: "worker", elapsed_seconds: 10 },
    { event: "node_finished", stage: "worker", elapsed_seconds: 11 },
    {
      event: "run_finished",
      stage: "runtime",
      elapsed_seconds: 12,
      task_status: "PAUSED",
    },
    { event: "run_started", stage: "runtime", elapsed_seconds: 0 },
    { event: "node_started", stage: "worker", elapsed_seconds: 1 },
  ].map((event) => JSON.stringify({ ...base, ...event })).join("\n");
  const state = projectAt(parseRecording(lines), 6);
  equal(
    state.visits.map((visit) => visit.status),
    ["finished", "active"],
    "visits",
  );
  equal(state.activeNode, "worker", "active node");
  equal(state.segments, 2, "segments");
});

Deno.test("reducer: duplicate cursor is ignored", () => {
  const base = {
    run_id: "run",
    timestamp: "2026-01-01T00:00:00Z",
    elapsed_seconds: 0,
  };
  const [event] = parseRecording(
    JSON.stringify({ ...base, event: "node_started", stage: "worker" }),
  );
  const state = initialRunState("run");
  const once = projectAt([event], 1, state);
  const twice = projectAt([event], 1, once);
  equal(twice.visits.length, 1, "visit count");
});
