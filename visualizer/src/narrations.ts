import { useEffect, useState } from "react";
import { boundedJson } from "./observations.ts";
import type { RunState } from "./reducer.ts";
import { snapshotGraph } from "./topology.ts";

export type Narration = {
  position: number;
  source_event_id: string;
  visit_id: string;
  stage: string;
  session_generation: number;
  source_position: number;
  source_timestamp: string;
  visit_started_at: string;
  message: string;
  method: "model" | "event_derived";
  status: "succeeded" | "failed";
};
export type NarrationPage = {
  status: "available" | "unavailable" | "unsupported_schema";
  items: Narration[];
  next_cursor: number;
};
const record = (v: unknown): Record<string, unknown> =>
  v !== null && typeof v === "object" && !Array.isArray(v)
    ? v as Record<string, unknown>
    : {};
const integer = (v: unknown): v is number =>
  typeof v === "number" && Number.isSafeInteger(v) && v >= 0;
const hash = (v: unknown): v is string =>
  typeof v === "string" && /^[a-f0-9]{64}$/.test(v);
const timestamp = (v: unknown): v is string =>
  typeof v === "string" && v.length <= 40 && Number.isFinite(Date.parse(v));
export function decodeNarrations(value: unknown, after: number): NarrationPage {
  const raw = record(value);
  if (raw.version !== 1) throw new Error("Unsupported narration version");
  if (raw.status === "unavailable" || raw.status === "unsupported_schema") {
    return { status: raw.status, items: [], next_cursor: after };
  }
  if (
    raw.status !== "available" || !Array.isArray(raw.items) ||
    raw.items.length > 200 || !integer(raw.next_cursor) ||
    raw.next_cursor < after
  ) throw new Error("Invalid narration page");
  let previous = after;
  const items = raw.items.map((value) => {
    const item = record(value);
    if (
      !integer(item.position) || item.position <= previous ||
      item.position > Number(raw.next_cursor) ||
      !integer(item.source_position) || !integer(item.session_generation) ||
      !hash(item.source_event_id) || !hash(item.visit_id) ||
      !timestamp(item.source_timestamp) || !timestamp(item.visit_started_at) ||
      !snapshotGraph.nodes.some((n) => n.id === item.stage) ||
      typeof item.message !== "string" || !item.message.trim() ||
      item.message.length > 320 ||
      !["model", "event_derived"].includes(String(item.method)) ||
      !["succeeded", "failed"].includes(String(item.status))
    ) throw new Error("Invalid narration item");
    previous = item.position;
    return {
      position: item.position,
      source_event_id: item.source_event_id,
      visit_id: item.visit_id,
      stage: String(item.stage),
      session_generation: item.session_generation,
      source_position: item.source_position,
      source_timestamp: item.source_timestamp,
      visit_started_at: item.visit_started_at,
      message: item.message,
      method: item.method as Narration["method"],
      status: item.status as Narration["status"],
    };
  });
  return { status: "available", items, next_cursor: raw.next_cursor };
}

export function latestNodeNarration(
  node: string,
  state: RunState,
  items: readonly Narration[],
): Narration | undefined {
  const visit = [...state.visits].reverse().find((v) => v.nodeId === node);
  return items.filter((item) =>
    item.stage === node && item.visit_started_at === visit?.startedTimestamp &&
    Date.parse(item.source_timestamp) <=
      Date.parse(state.lastEvent?.payload.timestamp ?? "")
  )
    .sort((a, b) =>
      b.session_generation - a.session_generation ||
      b.source_position - a.source_position
    )[0];
}

export function eventNodeBlurb(node: string, state: RunState): string {
  const visit = [...state.visits].reverse().find((v) => v.nodeId === node);
  if (!visit) return "No activity has been recorded for this step.";
  if (visit.status === "waiting") {
    return "Waiting for a decision, feedback, or a prerequisite to be resolved.";
  }
  if (visit.status === "failed") {
    return "An error stopped this step. Its result has not been accepted.";
  }
  if (visit.status === "finished") {
    return "This step finished. Further verification or review may still be required.";
  }
  const call = visit.calls.at(-1);
  if (call?.status === "failed") {
    return "The latest attempt reported an error. Waiting for the next recorded action.";
  }
  if (call?.status === "succeeded") {
    return "The latest attempt returned; this step has not yet reported completion.";
  }
  const actions: Record<string, string> = {
    worker:
      "Implementing the assigned changes. Verification is still required.",
    prover: "Checking the task’s results against the required verification.",
    roadmap: "Organizing the requested work into phases.",
    roadmap_review: "Reviewing the proposed phases and their dependencies.",
    architect: "Preparing the task plan for the current phase.",
    plan_review: "Reviewing the proposed task plan before work begins.",
    plan_revision: "Revising the task plan using the review findings.",
    intake_draft:
      "Reviewing the request and drafting requirements for your approval.",
    arbiter: "Assessing the recorded problem and proposing a recovery action.",
    recovery_dispatch: "Dispatching the admitted recovery action.",
    recovery_result:
      "Assessing the recovery result before deciding what follows.",
    gatekeeper: "Reviewing the completed work and its verification evidence.",
    final_review: "Checking the final completion requirements.",
  };
  return actions[node] ??
    "Working through this step’s assigned checks. No final result has been reported yet.";
}

/** One current-visit display value shared by the node and its popup. */
export function tickerForNode(
  node: string,
  state: RunState,
  items: readonly Narration[],
) {
  const visit = [...state.visits].reverse().find((v) => v.nodeId === node);
  if (node !== state.dotNode || !visit || visit.segment !== state.segments) {
    return undefined;
  }
  const narration = latestNodeNarration(node, state, items);
  return {
    message: narration?.message ?? eventNodeBlurb(node, state),
    source: narration?.method === "model" ? "Activity" : "Event summary",
  };
}

export function useNodeNarrations(runId: string | null) {
  const [items, setItems] = useState<Narration[]>([]);
  const [status, setStatus] = useState<NarrationPage["status"]>("unavailable");
  useEffect(() => {
    setItems([]);
    setStatus("unavailable");
    if (!runId) return;
    let active = true, cursor = 0;
    let next: ReturnType<typeof setTimeout> | undefined;
    let timeout: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;
    const poll = async () => {
      controller = new AbortController();
      timeout = globalThis.setTimeout(() => controller?.abort(), 8000);
      let more = false;
      try {
        const response = await fetch(
          `/api/v1/runs/${
            encodeURIComponent(runId)
          }/narrations?after=${cursor}&limit=100`,
          { signal: controller.signal, cache: "no-store" },
        );
        if (!response.ok) throw new Error("Narration unavailable");
        const page = decodeNarrations(await boundedJson(response), cursor);
        if (active) {
          setStatus(page.status);
          if (page.status === "available") {
            cursor = page.next_cursor;
            more = page.items.length === 100;
            setItems((old) =>
              [...new Map([...old, ...page.items].map((i) => [i.position, i]))
                .values()].slice(-1000)
            );
          }
        }
      } catch {
        if (active) setStatus("unavailable");
      } finally {
        globalThis.clearTimeout(timeout);
        if (active) {
          next = globalThis.setTimeout(() => void poll(), more ? 0 : 2000);
        }
      }
    };
    void poll();
    return () => {
      active = false;
      controller?.abort();
      globalThis.clearTimeout(next);
      globalThis.clearTimeout(timeout);
    };
  }, [runId]);
  return { items, status };
}
