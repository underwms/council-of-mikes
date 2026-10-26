export type GraphNode = {
  id: string;
  label: string;
  x: number;
  y: number;
  kind?: "boundary";
};
export type GraphEdge = {
  source: string;
  target: string;
  label?: string;
  kind?: "phase-loop" | "conditional";
};
export type GraphManifest = {
  schemaVersion: 1;
  graphVersion: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
};

// Read-only source snapshot; this is not the identity of an observed historical run.
export const snapshotGraph: GraphManifest = {
  schemaVersion: 1,
  graphVersion: "council-0.2.43-source-snapshot",
  nodes: [
    { id: "__start__", label: "START", x: 40, y: 280, kind: "boundary" },
    { id: "roadmap", label: "Roadmap", x: 250, y: 70 },
    { id: "roadmap_review", label: "Roadmap review", x: 480, y: 70 },
    { id: "governor", label: "Governor", x: 480, y: 310 },
    { id: "architect", label: "Architect", x: 680, y: 240 },
    { id: "plan_review", label: "Plan review", x: 900, y: 140 },
    { id: "plan_revision", label: "Plan revision", x: 900, y: 330 },
    { id: "strategy_reset", label: "Strategy reset", x: 900, y: 520 },
    { id: "plan_blocked", label: "Plan blocked", x: 680, y: 520 },
    { id: "worker", label: "Worker", x: 1130, y: 140 },
    { id: "prover", label: "Prover", x: 1360, y: 140 },
    { id: "investigation", label: "Investigation", x: 1360, y: 330 },
    { id: "phase_complete", label: "Phase complete", x: 1590, y: 140 },
    { id: "gatekeeper", label: "Gatekeeper", x: 1820, y: 140 },
    { id: "final_review", label: "Final review", x: 2050, y: 140 },
    { id: "__end__", label: "END", x: 2280, y: 280, kind: "boundary" },
  ],
  edges: [
    { source: "__start__", target: "roadmap", label: "phased" },
    { source: "__start__", target: "architect", label: "legacy" },
    { source: "roadmap", target: "roadmap_review" },
    { source: "roadmap", target: "__end__", label: "failed" },
    { source: "roadmap_review", target: "architect", label: "approved" },
    {
      source: "roadmap_review",
      target: "governor",
      label: "governed approval",
    },
    { source: "governor", target: "architect", label: "next eligible piece" },
    { source: "governor", target: "plan_blocked", label: "decision needed" },
    { source: "governor", target: "gatekeeper", label: "all pieces complete" },
    { source: "governor", target: "__end__", label: "failed" },
    { source: "roadmap_review", target: "roadmap", label: "revise" },
    { source: "roadmap_review", target: "plan_blocked", label: "blocked" },
    { source: "roadmap_review", target: "__end__", label: "failed" },
    { source: "architect", target: "plan_review", label: "plan ready" },
    { source: "architect", target: "plan_revision", label: "revision" },
    { source: "architect", target: "__end__", label: "failed" },
    { source: "plan_review", target: "worker", label: "approved" },
    { source: "plan_review", target: "plan_revision", label: "revise" },
    { source: "plan_review", target: "strategy_reset", label: "rethink" },
    { source: "plan_review", target: "plan_blocked", label: "blocked" },
    {
      source: "plan_review",
      target: "governor",
      label: "rework or blocked piece",
    },
    { source: "plan_review", target: "__end__", label: "failed" },
    { source: "plan_revision", target: "plan_review", label: "review" },
    {
      source: "plan_revision",
      target: "plan_revision",
      label: "preflight retry",
    },
    { source: "plan_revision", target: "plan_blocked", label: "blocked" },
    { source: "plan_revision", target: "governor", label: "blocked piece" },
    { source: "plan_revision", target: "__end__", label: "failed" },
    { source: "strategy_reset", target: "plan_review", label: "review" },
    {
      source: "strategy_reset",
      target: "plan_revision",
      label: "preflight retry",
    },
    { source: "strategy_reset", target: "plan_blocked", label: "blocked" },
    { source: "strategy_reset", target: "governor", label: "blocked piece" },
    { source: "strategy_reset", target: "__end__", label: "failed" },
    { source: "plan_blocked", target: "plan_revision", label: "feedback" },
    { source: "plan_blocked", target: "roadmap", label: "roadmap feedback" },
    { source: "plan_blocked", target: "__end__", label: "failed" },
    { source: "worker", target: "prover" },
    { source: "worker", target: "__end__", label: "failed" },
    { source: "prover", target: "investigation", label: "retrying" },
    { source: "prover", target: "worker", label: "executing" },
    { source: "prover", target: "phase_complete", label: "phase verified" },
    { source: "prover", target: "gatekeeper", label: "legacy verified" },
    { source: "prover", target: "__end__", label: "failed" },
    { source: "investigation", target: "worker" },
    { source: "investigation", target: "__end__", label: "failed" },
    {
      source: "phase_complete",
      target: "architect",
      label: "next phase",
      kind: "phase-loop",
    },
    {
      source: "phase_complete",
      target: "governor",
      label: "piece verified",
      kind: "phase-loop",
    },
    {
      source: "phase_complete",
      target: "gatekeeper",
      label: "all phases done",
    },
    { source: "phase_complete", target: "__end__", label: "failed" },
    { source: "gatekeeper", target: "final_review" },
    { source: "gatekeeper", target: "__end__", label: "failed" },
    { source: "final_review", target: "__end__" },
  ],
};

// Keep the established delivery layout, with intake before it and recovery below it.
for (const node of snapshotGraph.nodes) {
  if (node.id !== "__start__") node.x += 500;
  if (node.id === "__end__") node.x += 460;
  if (node.id === "final_review") node.x += 460;
}
snapshotGraph.nodes.push(
  { id: "intake_draft", label: "Requirements draft", x: 250, y: 70 },
  {
    id: "requirements_gate",
    label: "Human requirements approval",
    x: 480,
    y: 70,
  },
  { id: "requirements_reopen", label: "Reopen requirements", x: 480, y: 520 },
  { id: "arbiter", label: "Arbiter", x: 1180, y: 850 },
  { id: "recovery_admit", label: "Recovery admission", x: 1410, y: 850 },
  { id: "recovery_dispatch", label: "Recovery dispatch", x: 1640, y: 850 },
  { id: "recovery_result", label: "Recovery result", x: 1870, y: 850 },
  { id: "proof_refresh", label: "Proof refresh", x: 2550, y: 330 },
  {
    id: "finished_change_review",
    label: "Finished-change review",
    x: 2780,
    y: 330,
  },
);

function addRoute(source: string, target: string, label?: string) {
  if (
    !snapshotGraph.edges.some((edge) =>
      edge.source === source && edge.target === target
    )
  ) {
    snapshotGraph.edges.push({ source, target, label });
  }
}

for (
  const [source, target, label] of [
    ["__start__", "intake_draft", "requirements input"],
    ["intake_draft", "requirements_gate", "draft ready"],
    ["requirements_gate", "intake_draft", "human feedback"],
    ["requirements_gate", "roadmap", "exact approval"],
    ["requirements_gate", "architect", "legacy policy approval"],
    ["requirements_reopen", "intake_draft", "scope reconsideration"],
    ["roadmap", "roadmap", "preflight revision"],
    ["roadmap", "plan_blocked", "blocked"],
    ["gatekeeper", "proof_refresh", "stale proof or review needed"],
    ["proof_refresh", "finished_change_review", "current proof"],
    ["finished_change_review", "phase_complete", "review accepted"],
    ["finished_change_review", "gatekeeper", "legacy review accepted"],
    ["arbiter", "recovery_admit", "recommendation"],
    ["recovery_admit", "recovery_dispatch", "admitted"],
    ["recovery_dispatch", "prover", "verify"],
    ["recovery_dispatch", "worker", "repair"],
    ["recovery_dispatch", "plan_revision", "replan"],
    ["recovery_dispatch", "plan_blocked", "human input"],
    ["recovery_result", "arbiter", "further recovery"],
    ["recovery_result", "prover", "verify"],
    ["recovery_result", "worker", "continue"],
    ["recovery_result", "investigation", "investigate"],
    ["recovery_result", "phase_complete", "phase verified"],
    ["recovery_result", "gatekeeper", "legacy verified"],
    ["recovery_result", "plan_blocked", "human input"],
  ]
) addRoute(source, target, label);

// recover_route is shared by these engine nodes, ahead of their ordinary routing.
for (
  const source of [
    "roadmap",
    "roadmap_review",
    "governor",
    "architect",
    "plan_review",
    "plan_revision",
    "strategy_reset",
    "worker",
    "prover",
    "investigation",
    "phase_complete",
    "gatekeeper",
    "proof_refresh",
    "finished_change_review",
  ]
) {
  addRoute(source, "requirements_reopen", "human scope decision");
  addRoute(source, "arbiter", "recovery needed");
  addRoute(source, "recovery_result", "dispatched recovery result");
  addRoute(source, "__end__", "failed");
}

for (
  const source of [
    "intake_draft",
    "requirements_gate",
    "requirements_reopen",
    "arbiter",
    "recovery_admit",
    "recovery_dispatch",
    "recovery_result",
  ]
) addRoute(source, "__end__", "failed");

for (const edge of snapshotGraph.edges) {
  if (
    [
      "human scope decision",
      "recovery needed",
      "dispatched recovery result",
      "failed",
    ].includes(edge.label ?? "")
  ) {
    edge.kind = "conditional";
  }
}
