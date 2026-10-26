import { parseRecording } from "../src/contracts.ts";
import { describeNode, readable } from "../src/nodeActivity.ts";
import { initialRunState, projectAt } from "../src/reducer.ts";
import { snapshotGraph } from "../src/topology.ts";

function assert(value: boolean, message: string): void {
  if (!value) throw new Error(message);
}

function equal(actual: unknown, expected: unknown): void {
  assert(
    JSON.stringify(actual) === JSON.stringify(expected),
    `${JSON.stringify(actual)} != ${JSON.stringify(expected)}`,
  );
}

const replay = { mode: "replay" as const, atEnd: false };
const live = { mode: "live" as const, atEnd: true, connected: true };
const base = { run_id: "run", timestamp: "2026-10-24T12:00:00Z" };
function recording(...events: Record<string, unknown>[]) {
  return parseRecording(
    events.map((event, index) =>
      JSON.stringify({
        ...base,
        elapsed_seconds: index,
        stage: "worker",
        ...event,
      })
    ).join("\n"),
  );
}

Deno.test("activity: every unvisited graph node has a purpose and honest status", () => {
  for (const node of snapshotGraph.nodes) {
    const activity = describeNode(node.id, initialRunState("run"), replay);
    assert(activity.purpose.length > 20, `Missing purpose for ${node.id}`);
    equal(activity.status, "unobserved");
    assert(activity.summary.includes("No activity recorded"), node.id);
    equal(activity.visitCount, 0);
  }
});

Deno.test("activity: replay end qualifies an open call and preserves recorded details", async () => {
  const events = parseRecording(
    await Deno.readTextFile("tests/fixtures/sample-events.jsonl"),
  );
  const activity = describeNode(
    "plan_review",
    projectAt(events, events.length),
    {
      mode: "replay",
      atEnd: true,
    },
  );
  equal(activity.status, "active");
  assert(activity.summary.includes("recording ends"), activity.summary);
  assert(activity.summary.includes("unknown"), activity.summary);
  equal(activity.visit?.calls.at(-1)?.number, 12);
  equal(activity.visit?.calls.at(-1)?.role, "reviewer");
});

Deno.test("activity: live call completion updates the same node without inventing a result", () => {
  const events = recording(
    { event: "run_started", stage: "runtime" },
    { event: "node_started" },
    {
      event: "call_started",
      stage: "model",
      call: 1,
      role: "coder",
      operation: "implementation",
    },
    { event: "call_succeeded", stage: "model", call: 1 },
    { event: "node_finished" },
  );
  const running = describeNode("worker", projectAt(events, 3), live);
  assert(running.summary.includes("in flight"), running.summary);
  const returned = describeNode("worker", projectAt(events, 4), live);
  assert(returned.summary.includes("returned"), returned.summary);
  const finished = describeNode("worker", projectAt(events, 5), live);
  equal(finished.status, "finished");
  assert(!finished.summary.includes("in flight"), finished.summary);
  equal(
    describeNode("worker", projectAt(events, 1), replay).status,
    "unobserved",
  );
});

Deno.test("activity: waiting and failed nodes take priority over stale open calls", () => {
  const events = recording(
    { event: "run_started", stage: "runtime" },
    { event: "node_started" },
    { event: "call_started", stage: "model", call: 1 },
    { event: "approval_waiting" },
    { event: "node_failed" },
  );
  const waiting = describeNode("worker", projectAt(events, 4), live);
  equal(waiting.status, "waiting");
  assert(waiting.summary.includes("approval"), waiting.summary);
  const failed = describeNode("worker", projectAt(events, 5), live);
  equal(failed.status, "failed");
  assert(!failed.summary.includes("in flight"), failed.summary);
});

Deno.test("activity: latest visit wins after resume even when elapsed time resets", () => {
  const events = recording(
    { event: "run_started", stage: "runtime" },
    { event: "node_started" },
    { event: "node_finished" },
    { event: "run_finished", stage: "runtime", task_status: "PAUSED" },
    { event: "run_started", stage: "runtime", elapsed_seconds: 0 },
    { event: "node_started", elapsed_seconds: 1 },
    {
      event: "inspection_round_started",
      inspection_round: 0,
      remaining_rounds: 0,
    },
  );
  const activity = describeNode(
    "worker",
    projectAt(events, events.length),
    live,
  );
  equal(activity.visitCount, 2);
  equal(activity.visit?.segment, 2);
  assert(
    describeNode("__start__", projectAt(events, events.length), live).summary
      .includes("2 run segments"),
    "Resumed runs must describe multiple observed segments",
  );
  equal(activity.visit?.inspectionRound, 0);
  equal(activity.status, "active");
});

Deno.test("activity: missing metadata and failed calls have readable fallbacks", () => {
  const events = recording(
    { event: "run_started", stage: "runtime" },
    { event: "node_started" },
    { event: "call_started", stage: "model", call: 0 },
    { event: "call_failed", stage: "model", call: 0 },
  );
  const running = describeNode("worker", projectAt(events, 3), live);
  assert(!running.summary.includes("undefined"), running.summary);
  assert(running.summary.includes("#0"), running.summary);
  const failed = describeNode("worker", projectAt(events, 4), live);
  assert(failed.summary.includes("failed"), failed.summary);
});

Deno.test("activity: stream interruption and runtime failure cannot claim current execution", () => {
  const events = recording(
    { event: "run_started", stage: "runtime" },
    { event: "node_started" },
    { event: "call_started", stage: "model", call: 1 },
    { event: "runtime_failed", stage: "runtime" },
    { event: "run_finished", stage: "runtime" },
  );
  const disconnected = describeNode("worker", projectAt(events, 3), {
    ...live,
    connected: false,
  });
  assert(disconnected.summary.includes("Last observed"), disconnected.summary);
  assert(disconnected.summary.includes("unavailable"), disconnected.summary);
  for (const position of [4, 5]) {
    const activity = describeNode("worker", projectAt(events, position), live);
    assert(activity.summary.includes("unknown"), activity.summary);
    assert(!activity.summary.includes("in flight"), activity.summary);
  }
});

Deno.test("activity: START and END use observed run boundaries without inventing success", () => {
  const events = recording(
    { event: "run_started", stage: "runtime" },
    { event: "run_finished", stage: "runtime" },
  );
  equal(
    describeNode("__start__", projectAt(events, 1), live).status,
    "finished",
  );
  equal(
    describeNode("__end__", projectAt(events, 1), live).status,
    "unobserved",
  );
  const end = describeNode("__end__", projectAt(events, 2), live);
  assert(end.summary.includes("unknown"), end.summary);
  const completed = recording(
    { event: "run_started", stage: "runtime" },
    { event: "run_finished", stage: "runtime", task_status: "COMPLETED" },
  );
  assert(
    describeNode("__end__", projectAt(completed, 2), live).summary.includes(
      "Completed",
    ),
    "Explicit terminal outcome must be displayed",
  );
  const failed = recording(
    { event: "run_started", stage: "runtime" },
    { event: "run_finished", stage: "runtime", task_status: "FAILED" },
  );
  equal(describeNode("__end__", projectAt(failed, 2), live).status, "failed");
});

Deno.test("activity: unknown stages and missing optional labels have safe display text", () => {
  const activity = describeNode("future_stage", initialRunState("run"), replay);
  assert(
    activity.purpose.includes("Council workflow"),
    "Unknown stage needs a purpose fallback",
  );
  equal(activity.status, "unobserved");
  equal(readable(undefined), "Not reported");
  equal(readable(""), "Not reported");
  equal(readable("planning_inspection"), "Planning Inspection");
});
