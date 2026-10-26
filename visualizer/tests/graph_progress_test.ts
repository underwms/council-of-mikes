import { parseRecording } from "../src/contracts.ts";
import {
  edgeAppearance,
  nodeIsAnimating,
  nodeIsCurrent,
  nodeStatusLabel,
  projectEdgeHistory,
} from "../src/graphProgress.ts";
import { projectAt } from "../src/reducer.ts";
import { snapshotGraph } from "../src/topology.ts";

function assert(value: boolean, message: string): void {
  if (!value) throw new Error(message);
}

function recording(...events: Record<string, unknown>[]) {
  return parseRecording(
    events.map((event, index) =>
      JSON.stringify({
        run_id: "progress",
        timestamp: "2026-10-24T16:00:00Z",
        elapsed_seconds: index,
        stage: "runtime",
        ...event,
      })
    ).join("\n"),
  );
}

Deno.test("progress: observed handoffs refresh recency without counting calls or duplicates", () => {
  const events = recording(
    { event: "run_started" },
    { event: "node_started", stage: "roadmap" },
    { event: "node_finished", stage: "roadmap" },
    { event: "node_started", stage: "roadmap_review" },
    { event: "call_started", stage: "model", call: 1 },
    { event: "node_started", stage: "roadmap" },
    { event: "node_started", stage: "roadmap_review" },
  );
  const history = projectEdgeHistory([...events, events[6]], 8, snapshotGraph);
  assert(
    history.totalTraversals === 4,
    "Only four observed handoffs should count",
  );
  const repeated = history.traversals.get("roadmap->roadmap_review")!;
  assert(
    repeated.count === 2 && repeated.lastOrder === 4,
    "Repeat handoff must refresh its recency",
  );
  assert(
    history.traversals.get("__start__->roadmap")?.lastOrder === 1,
    "Initial route should remain in history",
  );
  assert(
    !history.traversals.has("__start__->architect"),
    "Unused legacy route must stay untraversed",
  );
  assert(
    !history.traversals.has("roadmap_review->__end__"),
    "An open run must not invent an end route",
  );
});

Deno.test("progress: rewind and resumed segments cannot invent a cross-segment route", () => {
  const events = recording(
    { event: "run_started" },
    { event: "node_started", stage: "worker" },
    { event: "run_finished", task_status: "COMPLETED" },
    { event: "run_started", elapsed_seconds: 0 },
    { event: "node_started", stage: "prover", elapsed_seconds: 1 },
    { event: "node_started", stage: "worker", elapsed_seconds: 2 },
  );
  const history = projectEdgeHistory(events, events.length, snapshotGraph);
  assert(
    !history.traversals.has("worker->prover"),
    "Resume must not join the two segments",
  );
  assert(
    history.traversals.has("worker->__end__"),
    "An observed run end should mark its actual end route",
  );
  assert(
    history.traversals.has("prover->worker"),
    "Same-segment handoff should be recorded despite elapsed reset",
  );
  assert(
    projectEdgeHistory(events, 2, snapshotGraph).totalTraversals === 0,
    "Rewind must remove future routes",
  );
  assert(
    projectEdgeHistory(events, 0, snapshotGraph).traversals.size === 0,
    "Restart must clear all routes",
  );
  assert(
    projectEdgeHistory([], 10, snapshotGraph).totalTraversals === 0,
    "A new empty recording has no history",
  );
});

Deno.test("progress: incomplete excerpts and unknown stages do not imply routes; self-loops remain visible", () => {
  const events = recording(
    { event: "node_started", stage: "architect" },
    { event: "node_started", stage: "future_stage" },
    { event: "node_started", stage: "plan_review" },
    { event: "node_started", stage: "plan_revision" },
    { event: "node_started", stage: "plan_revision" },
    { event: "runtime_failed" },
    { event: "node_started", stage: "plan_revision" },
    { event: "run_finished", task_status: "COMPLETED" },
  );
  const history = projectEdgeHistory(events, events.length, snapshotGraph);
  assert(
    !history.traversals.has("__start__->architect"),
    "Missing run start must not be invented",
  );
  assert(
    !history.traversals.has("architect->plan_review"),
    "Unknown intermediate stage must not be skipped",
  );
  assert(
    history.traversals.get("plan_revision->plan_revision")?.count === 1,
    "Observed self-loop should count",
  );
  assert(
    history.traversals.has("plan_revision->__end__"),
    "Explicit end should survive a partial excerpt",
  );
});

Deno.test("progress: recent edges are stronger while arbitrarily old traversals remain clear", () => {
  const unused = edgeAppearance(undefined, 200);
  const recent = edgeAppearance({ count: 1, lastOrder: 200 }, 200);
  const older = edgeAppearance({ count: 1, lastOrder: 195 }, 200);
  const oldest = edgeAppearance({ count: 1, lastOrder: 1 }, 10000);
  assert(
    !unused.visited && recent.visited && oldest.visited,
    "Visited and unused edges must stay distinct",
  );
  assert(
    recent.width > older.width && older.width >= oldest.width,
    "Line weight should fade by recency",
  );
  assert(
    oldest.width > unused.width && oldest.width >= 1.8,
    "Old routes must retain a visible stroke floor",
  );
  assert(
    recent.endColor !== older.endColor,
    "Recency must also change the gradient color",
  );
  assert(
    recent.startColor !== recent.endColor &&
      oldest.startColor !== oldest.endColor,
    "Visited edges need directional gradients at every age",
  );
});

Deno.test("progress: active animation stops at completion, waiting, interruption and unavailable observation", () => {
  const events = recording(
    { event: "run_started" },
    { event: "node_started", stage: "worker" },
    { event: "approval_waiting", stage: "worker" },
    { event: "node_finished", stage: "worker" },
    { event: "node_started", stage: "plan_blocked" },
    { event: "runtime_failed" },
    { event: "run_finished", task_status: "COMPLETED" },
  );
  const live = { mode: "live" as const, atEnd: true, connected: true };
  const active = projectAt(events, 2);
  assert(
    nodeIsCurrent("worker", active),
    "Worker should be current after its start",
  );
  assert(
    nodeIsAnimating("worker", active, live),
    "Connected active node should bounce",
  );
  assert(
    !nodeIsAnimating("prover", active, live),
    "Unvisited node must not bounce",
  );
  assert(
    !nodeIsAnimating("worker", active, { ...live, connected: false }),
    "Disconnected activity must not bounce",
  );
  assert(
    !nodeIsAnimating("worker", active, { mode: "replay", atEnd: true }),
    "Incomplete recording end must not imply live activity",
  );
  assert(
    nodeIsAnimating("worker", active, { mode: "replay", atEnd: false }),
    "Replay should indicate the active node at its position",
  );
  assert(
    nodeIsCurrent("worker", projectAt(events, 3)),
    "Waiting can still be the current node",
  );
  for (const position of [3, 4, 6, 7]) {
    assert(
      !nodeIsAnimating(
        projectAt(events, position).activeNode ?? "worker",
        projectAt(events, position),
        live,
      ),
      `Position ${position} must not bounce`,
    );
  }
  assert(
    nodeIsCurrent("plan_blocked", projectAt(events, 5)),
    "Plan Blocked can be current",
  );
  assert(
    !nodeIsCurrent("plan_blocked", projectAt(events, 7)),
    "Ended run has no executing current node",
  );
  const resumed = recording(
    { event: "run_started" },
    { event: "node_started", stage: "worker" },
    { event: "run_started" },
  );
  assert(
    !nodeIsCurrent("worker", projectAt(resumed, 3)),
    "New segment must not animate an old visit",
  );
});

Deno.test("progress: completed node status displays Visited without changing diagnostic state", () => {
  const events = recording({ event: "node_started", stage: "worker" }, {
    event: "node_finished",
    stage: "worker",
  });
  const state = projectAt(events, events.length);
  assert(
    nodeStatusLabel(state.visits[0].status) === "Visited",
    "Completed display should say Visited",
  );
  assert(
    state.visits[0].status === "finished",
    "Diagnostic completion status must remain intact",
  );
  assert(
    nodeStatusLabel("unobserved") === "Not observed",
    "Unvisited display should remain readable",
  );
  assert(
    nodeStatusLabel("active") === "Active" &&
      nodeStatusLabel("waiting") === "Waiting" &&
      nodeStatusLabel("failed") === "Failed",
    "Other statuses should retain their meaning",
  );
});

Deno.test("progress: approval pauses and unknown endings do not traverse END", () => {
  for (const status of [undefined, "PAUSED", "BLOCKED", "PLAN_ONLY"]) {
    const events = recording(
      { event: "run_started" },
      { event: "node_started", stage: "requirements_gate" },
      { event: "approval_waiting", stage: "requirements_gate" },
      { event: "run_finished", task_status: status },
    );
    assert(
      !projectEdgeHistory(events, events.length, snapshotGraph).traversals.has(
        "requirements_gate->__end__",
      ),
      "Session closure is not a graph END traversal",
    );
  }
});

Deno.test("progress: batched approval handoff uses latest observed transition without bridging resume", () => {
  const events = recording(
    { event: "run_started" },
    { event: "node_started", stage: "requirements_gate" },
    { event: "approval_waiting", stage: "requirements_gate" },
    { event: "run_finished" },
    { event: "run_started" },
    { event: "node_started", stage: "requirements_gate" },
    { event: "node_finished", stage: "requirements_gate" },
    { event: "node_started", stage: "roadmap" },
    { event: "call_started", stage: "model", call: 1 },
  );
  const history = projectEdgeHistory(events, events.length, snapshotGraph);
  assert(
    history.latest?.source === "requirements_gate" &&
      history.latest.target === "roadmap" && history.latest.position === 8,
    "Batch must retain actual approval transition",
  );
  const resumed = projectEdgeHistory(events, 6, snapshotGraph);
  assert(!resumed.latest, "Resumed node is not a cross-session handoff");
  assert(
    !history.traversals.has("requirements_gate->__end__"),
    "Approval wait must not color END",
  );
});

Deno.test("progress: real diagnostic failure closes END without a task_status field", () => {
  const events = recording(
    { event: "run_started" },
    { event: "node_started", stage: "worker" },
    { event: "node_failed", stage: "worker" },
    { event: "run_finished" },
  );
  assert(
    projectEdgeHistory(events, events.length, snapshotGraph).traversals.has(
      "worker->__end__",
    ),
    "Real failed-node ending must remain visible",
  );
});
Deno.test("progress: resumed roadmap is not a second START route", () => {
  const events = recording(
    { event: "run_started" },
    { event: "node_started", stage: "intake_draft" },
    { event: "run_finished" },
    { event: "run_started" },
    { event: "node_started", stage: "roadmap" },
  );
  assert(
    !projectEdgeHistory(events, events.length, snapshotGraph).traversals.has(
      "__start__->roadmap",
    ),
    "Resume is not a fresh graph START",
  );
});

Deno.test("progress: closed observation clears teal emphasis while preserving history", () => {
  const recent = edgeAppearance({ count: 1, lastOrder: 1 }, 1);
  const stopped = edgeAppearance({ count: 1, lastOrder: 1 }, 1, false);
  const old = edgeAppearance({ count: 1, lastOrder: 1 }, 10000);
  assert(
    stopped.visited && stopped.endColor === old.endColor &&
      stopped.width === old.width,
    "Stopped observation must use muted history styling",
  );
  assert(
    stopped.endColor !== recent.endColor,
    "Current teal cannot remain after stopping",
  );
});
Deno.test("progress: completed delivery closes END, while unknown delivery does not", () => {
  for (const status of ["COMPLETED", "injected", undefined]) {
    const events = recording(
      { event: "run_started" },
      { event: "node_started", stage: "final_review" },
      { event: "node_finished", stage: "final_review" },
      { event: "delivery_state", stage: "final_review", run_status: status },
      { event: "run_finished" },
    );
    assert(
      projectEdgeHistory(events, events.length, snapshotGraph).traversals.has(
        "final_review->__end__",
      ) === (status === "COMPLETED"),
      "Only allowlisted terminal delivery is evidence of END",
    );
  }
});
