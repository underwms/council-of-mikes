import type { NodeVisit, RunState } from "./reducer.ts";

export type ObservationContext = {
  mode: "live" | "replay";
  atEnd: boolean;
  connected?: boolean;
};

export type NodeActivity = {
  purpose: string;
  status: NodeVisit["status"] | "unobserved";
  summary: string;
  visit?: NodeVisit;
  visitCount: number;
};

const purposes: Record<string, string> = {
  intake_draft:
    "Investigates read-only and drafts requirements, baseline facts and unresolved questions for the human.",
  requirements_gate:
    "Waits for human feedback or approval of the exact requirements hash. Autonomous approval cannot cross this boundary.",
  requirements_reopen:
    "Returns a material scope decision to human requirements drafting and exact reapproval while preserving history.",
  arbiter:
    "Assesses a failure and proposes bounded recovery through the single shared arbiter mechanism.",
  recovery_admit:
    "Checks the recovery recommendation against accepted contracts, evidence and cumulative budgets before admission.",
  recovery_dispatch:
    "Dispatches an admitted repair, replan or verification action; recommendation alone is not execution.",
  recovery_result:
    "Assesses the actual recovery result and routes to verification, continued work or further bounded arbitration.",
  proof_refresh:
    "Restores saved delivery contracts so stale evidence can be refreshed or finished work independently reviewed.",
  finished_change_review:
    "Independently reviews the finished content, requirements, documentation and current proof; findings return through the arbiter or human scope boundary.",
  __start__: "Starts or resumes the Council run and routes it into planning.",
  roadmap:
    "Breaks the requested work into ordered phases and inspects the relevant project context.",
  roadmap_review:
    "Reviews the proposed phases for scope, dependencies, and a workable delivery order.",
  governor:
    "Schedules one eligible work piece, preserves its plan and evidence, and coordinates blockers and contract versions.",
  architect:
    "Inspects the project and creates an executable task plan for the current phase.",
  plan_review:
    "Checks the task plan, prerequisites, and verification requirements before work begins.",
  plan_revision:
    "Revises the task plan using review findings and prerequisite checks.",
  strategy_reset:
    "Rethinks a stalled plan and resolves dependency or approach problems before another review.",
  plan_blocked:
    "Stops planning at a blocker that needs a decision, feedback, or changed conditions.",
  worker:
    "Implements the current approved assignment, including scoped finalization polish when requested, using accepted requirements, baseline and plan context.",
  prover:
    "Runs the task's verification commands and checks whether the observed results meet its requirements.",
  investigation:
    "Investigates a verification failure and prepares guidance for a bounded repair attempt.",
  phase_complete:
    "Closes the verified phase and moves to the next phase or the final quality checks.",
  gatekeeper:
    "Audits the completed work and verification evidence before final review.",
  final_review:
    "Performs the final completion gate, including approval when manual review is enabled.",
  __end__:
    "Marks the end of a run segment. The reported task outcome determines whether the work succeeded.",
};

export function readable(value: string | undefined): string {
  return value
    ? value.toLowerCase().replaceAll("_", " ").replace(
      /\b\w/g,
      (letter) => letter.toUpperCase(),
    )
    : "Not reported";
}

function visitSummary(visit: NodeVisit): string {
  if (visit.status === "failed") {
    return "This node reported a failure. Its work did not finish successfully.";
  }
  if (visit.status === "finished") {
    return "This visit has finished. It is no longer executing at this node.";
  }
  if (visit.status === "waiting") {
    return "Waiting for approval or feedback before execution can continue.";
  }
  const call = visit.calls.at(-1);
  if (call?.status === "running") {
    return `Model call #${call.number} is in flight. No result has been observed yet.`;
  }
  if (call?.status === "failed") {
    return `Model call #${call.number} failed. No later model activity has been recorded at this node.`;
  }
  if (call?.status === "succeeded") {
    return `Model call #${call.number} returned. The stage has not reported completion yet.`;
  }
  return "This stage is active. No model call is currently recorded for this visit.";
}

export function describeNode(
  nodeId: string,
  state: RunState,
  context: ObservationContext,
): NodeActivity {
  const visits = state.visits.filter((visit) => visit.nodeId === nodeId);
  const visit = visits.at(-1);
  const activity: NodeActivity = {
    purpose: purposes[nodeId] ?? "Executes a stage of the Council workflow.",
    status: visit?.status ?? "unobserved",
    summary:
      "No activity recorded for this node at the current observation position.",
    visit,
    visitCount: visits.length,
  };
  if (nodeId === "__start__" && state.segments > 0) {
    activity.status = "finished";
    activity.summary = `Run start observed (${state.segments} run segment${
      state.segments === 1 ? "" : "s"
    }).`;
  } else if (nodeId === "__end__" && state.segments > 0 && !state.segmentOpen) {
    activity.status = state.taskStatus === "FAILED" ? "failed" : "finished";
    activity.summary = state.taskStatus === "unknown"
      ? "The run segment ended; the task outcome is unknown."
      : `The run segment ended. Task outcome: ${readable(state.taskStatus)}.`;
  } else if (visit) {
    const unfinished = visit.status === "active" || visit.status === "waiting";
    const interrupted = state.lastEvent?.payload.event === "runtime_failed" ||
      (state.segments > 0 && !state.segmentOpen);
    if (unfinished && interrupted) {
      activity.summary =
        "Observation stopped before this visit finished. Its current activity and task outcome are unknown.";
    } else if (unfinished && context.mode === "replay" && context.atEnd) {
      activity.summary =
        "The recording ends before this visit finishes. Its current activity and task outcome are unknown.";
    } else {
      activity.summary = visitSummary(visit);
    }
  }
  if (context.mode === "live" && context.connected === false) {
    activity.summary =
      `Last observed: ${activity.summary} Live updates are unavailable.`;
  }
  return activity;
}
