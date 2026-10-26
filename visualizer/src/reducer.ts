import type { EventEnvelope } from "./contracts.ts";

export type CallVisit = {
  number: number;
  role?: string;
  operation?: string;
  status: "running" | "succeeded" | "failed";
  startedAt: number;
  finishedAt?: number;
};

export type NodeVisit = {
  nodeId: string;
  ordinal: number;
  segment: number;
  status: "active" | "finished" | "failed" | "waiting";
  startedAt: number;
  startedTimestamp?: string;
  finishedAt?: number;
  inspectionRound?: number;
  remainingRounds?: number;
  calls: CallVisit[];
};

export type RunState = {
  runId: string;
  recordingId?: string;
  appliedCursors: string[];
  segments: number;
  segmentOpen: boolean;
  activeNode?: string;
  dotNode?: string;
  taskStatus: string;
  functionalComplete: boolean | null;
  prReady: boolean | null;
  visits: NodeVisit[];
  lastEvent?: EventEnvelope;
  notices: string[];
};

export function initialRunState(runId: string): RunState {
  return {
    runId,
    appliedCursors: [],
    segments: 0,
    segmentOpen: false,
    taskStatus: "unknown",
    functionalComplete: null,
    prReady: null,
    visits: [],
    notices: [],
  };
}

export function applyEvent(state: RunState, envelope: EventEnvelope): RunState {
  if (
    envelope.payload.run_id !== state.runId ||
    state.appliedCursors.includes(envelope.cursor)
  ) {
    return state;
  }
  const next: RunState = {
    ...state,
    recordingId: envelope.recordingId,
    appliedCursors: [...state.appliedCursors, envelope.cursor],
    visits: state.visits.map((visit) => ({
      ...visit,
      calls: visit.calls.map((call) => ({ ...call })),
    })),
    notices: [...state.notices],
    lastEvent: envelope,
  };
  const event = envelope.payload;
  const activeVisit = [...next.visits].reverse().find((visit) =>
    visit.status === "active" || visit.status === "waiting"
  );
  switch (event.event) {
    case "run_started":
      next.segments++;
      next.segmentOpen = true;
      next.taskStatus = "unknown";
      break;
    case "run_finished":
      next.segmentOpen = false;
      if (event.task_status) next.taskStatus = event.task_status;
      break;
    case "node_started":
      if (event.stage === "requirements_reopen") {
        next.functionalComplete = null;
        next.prReady = null;
      }
      if (activeVisit) activeVisit.status = "finished";
      next.visits.push({
        nodeId: event.stage,
        ordinal: next.visits.length + 1,
        segment: next.segments,
        status: "active",
        startedAt: event.elapsed_seconds,
        startedTimestamp: event.timestamp,
        calls: [],
      });
      next.activeNode = event.stage;
      next.dotNode = event.stage;
      break;
    case "node_finished":
    case "node_failed": {
      const visit = [...next.visits].reverse().find((item) =>
        item.nodeId === event.stage &&
        (item.status === "active" || item.status === "waiting")
      );
      if (visit) {
        visit.status = event.event === "node_failed" ? "failed" : "finished";
        visit.finishedAt = event.elapsed_seconds;
      }
      if (next.activeNode === event.stage) next.activeNode = undefined;
      break;
    }
    case "approval_waiting":
    case "planning_blocked":
      if (activeVisit) activeVisit.status = "waiting";
      break;
    case "delivery_state":
      next.functionalComplete = event.functional_complete ?? null;
      next.prReady = event.pr_ready ?? null;
      break;
    case "inspection_round_started":
      if (activeVisit && activeVisit.nodeId === event.stage) {
        activeVisit.inspectionRound = event.inspection_round;
        activeVisit.remainingRounds = event.remaining_rounds;
      }
      break;
    case "call_started":
      if (activeVisit && event.call !== undefined) {
        activeVisit.calls.push({
          number: event.call,
          role: event.role,
          operation: event.operation,
          status: "running",
          startedAt: event.elapsed_seconds,
        });
      } else if (event.call !== undefined) {
        next.notices.push(`Call ${event.call} has no enclosing active node`);
      }
      break;
    case "call_succeeded":
    case "call_failed": {
      const call = [...(activeVisit?.calls ?? [])].reverse().find((item) =>
        item.number === event.call && item.status === "running"
      );
      if (call) {
        call.status = event.event === "call_succeeded" ? "succeeded" : "failed";
        call.finishedAt = event.elapsed_seconds;
      }
      break;
    }
    case "runtime_failed":
      next.notices.push(
        "Runtime failure reported; task outcome is not confirmed",
      );
      break;
    case "inspection_budget_reached":
      next.notices.push("Inspection budget reached");
      break;
  }
  return next;
}

export function projectAt(
  events: readonly EventEnvelope[],
  position: number,
  base?: RunState,
): RunState {
  const first = events[0];
  let state = base ?? initialRunState(first?.payload.run_id ?? "unknown");
  for (const event of events.slice(0, Math.max(0, position))) {
    state = applyEvent(state, event);
  }
  return state;
}
