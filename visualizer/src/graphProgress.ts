import type { EventEnvelope } from "./contracts.ts";
import type { ObservationContext } from "./nodeActivity.ts";
import type { NodeVisit, RunState } from "./reducer.ts";
import type { GraphManifest } from "./topology.ts";

export type EdgeTraversal = { count: number; lastOrder: number };
export type Transition = {
  source: string;
  target: string;
  cursor: string;
  position: number;
};
export type EdgeHistory = {
  latest?: Transition;
  traversals: ReadonlyMap<string, EdgeTraversal>;
  totalTraversals: number;
};

export function projectEdgeHistory(
  events: readonly EventEnvelope[],
  position: number,
  graph: GraphManifest,
): EdgeHistory {
  const allowed = new Set(
    graph.edges.map((edge) => `${edge.source}->${edge.target}`),
  );
  const traversals = new Map<string, EdgeTraversal>();
  const seen = new Set<string>();
  const runId = events[0]?.payload.run_id;
  let previous: string | undefined;
  let segments = 0;
  let failedNode: string | undefined;
  let terminalStatus: string | undefined;
  let totalTraversals = 0;
  let latest: Transition | undefined;
  let currentEnvelope: EventEnvelope;
  let currentPosition = 0;
  function traverse(target: string) {
    const key = `${previous}->${target}`;
    if (!previous || !allowed.has(key)) return;
    latest = {
      source: previous,
      target,
      cursor: currentEnvelope.cursor,
      position: currentPosition,
    };
    totalTraversals++;
    traversals.set(key, {
      count: (traversals.get(key)?.count ?? 0) + 1,
      lastOrder: totalTraversals,
    });
  }
  for (const envelope of events.slice(0, Math.max(0, position))) {
    currentEnvelope = envelope;
    currentPosition++;
    if (envelope.payload.run_id !== runId || seen.has(envelope.cursor)) {
      continue;
    }
    seen.add(envelope.cursor);
    const event = envelope.payload;
    if (event.event === "run_started") {
      previous = segments++ === 0 ? "__start__" : undefined;
      failedNode = undefined;
      terminalStatus = undefined;
      latest = undefined;
    } else if (event.event === "node_started") {
      latest = undefined;
      failedNode = undefined;
      terminalStatus = undefined;
      traverse(event.stage);
      previous = event.stage;
    } else if (event.event === "node_failed") {
      failedNode = event.stage;
    } else if (event.event === "delivery_state") {
      terminalStatus = event.run_status;
    } else if (
      event.event === "approval_waiting" || event.event === "planning_blocked"
    ) {
      failedNode = undefined;
      terminalStatus = undefined;
      latest = undefined;
    } else if (event.event === "run_finished") {
      latest = undefined;
      if (
        event.task_status === "COMPLETED" || event.task_status === "FAILED" ||
        terminalStatus === "COMPLETED" ||
        (failedNode !== undefined && failedNode === previous)
      ) traverse("__end__");
      previous = undefined;
    } else if (event.event === "runtime_failed") {
      previous = undefined;
      latest = undefined;
      failedNode = undefined;
      terminalStatus = undefined;
    }
  }
  return { traversals, totalTraversals, latest };
}

function blendColor(older: string, recent: string, strength: number): string {
  const channels = [1, 3, 5].map((offset) => {
    const start = parseInt(older.slice(offset, offset + 2), 16);
    const end = parseInt(recent.slice(offset, offset + 2), 16);
    return Math.round(start + (end - start) * strength).toString(16).padStart(
      2,
      "0",
    );
  });
  return `#${channels.join("")}`;
}

export function edgeAppearance(
  traversal: EdgeTraversal | undefined,
  totalTraversals: number,
  highlightRecent = true,
) {
  if (!traversal) {
    return {
      visited: false,
      startColor: "#c4d2dc",
      endColor: "#c4d2dc",
      width: 1.2,
    };
  }
  const age = Math.max(0, totalTraversals - traversal.lastOrder);
  const strength = highlightRecent ? Math.exp(-age / 6) : 0;
  return {
    visited: true,
    startColor: blendColor("#b4c2cc", "#59b9c9", strength),
    endColor: blendColor("#8da1af", "#006d83", strength),
    width: 1.8 + 2.2 * strength,
  };
}

export function nodeIsCurrent(nodeId: string, state: RunState): boolean {
  const visit = [...state.visits].reverse().find((entry) =>
    entry.nodeId === nodeId
  );
  return state.activeNode === nodeId && visit?.segment === state.segments &&
    (visit.status === "active" || visit.status === "waiting") &&
    (state.segments === 0 || state.segmentOpen) &&
    state.lastEvent?.payload.event !== "runtime_failed";
}

export function nodeIsAnimating(
  nodeId: string,
  state: RunState,
  context: ObservationContext,
): boolean {
  if (!nodeIsCurrent(nodeId, state)) return false;
  const visit = [...state.visits].reverse().find((entry) =>
    entry.nodeId === nodeId
  );
  return visit?.status === "active" &&
    (context.mode === "live" ? context.connected === true : !context.atEnd);
}

export function nodeStatusLabel(
  status: NodeVisit["status"] | "unobserved",
): string {
  if (status === "finished") return "Visited";
  if (status === "unobserved") return "Not observed";
  return status[0].toUpperCase() + status.slice(1);
}
