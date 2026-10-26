export type GroupId = "requirements" | "delivery" | "recovery" | "final";

export const graphGroups: {
  id: GroupId;
  label: string;
  anchor: string;
  nodes: string[];
}[] = [
  {
    id: "requirements",
    label: "Requirements",
    anchor: "intake_draft",
    nodes: ["intake_draft", "requirements_gate", "requirements_reopen"],
  },
  {
    id: "delivery",
    label: "Planning & delivery",
    anchor: "roadmap",
    nodes: [
      "roadmap",
      "roadmap_review",
      "governor",
      "architect",
      "plan_review",
      "plan_revision",
      "strategy_reset",
      "plan_blocked",
      "worker",
      "prover",
      "investigation",
      "phase_complete",
    ],
  },
  {
    id: "recovery",
    label: "Recovery",
    anchor: "arbiter",
    nodes: [
      "arbiter",
      "recovery_admit",
      "recovery_dispatch",
      "recovery_result",
    ],
  },
  {
    id: "final",
    label: "Final checks",
    anchor: "gatekeeper",
    nodes: [
      "gatekeeper",
      "proof_refresh",
      "finished_change_review",
      "final_review",
    ],
  },
];

export function groupForNode(nodeId: string): GroupId | undefined {
  return graphGroups.find((group) => group.nodes.includes(nodeId))?.id;
}

export function groupNodeClass(
  nodeId: string,
  selected: GroupId | null,
): string {
  if (!selected) return "";
  return groupForNode(nodeId) === selected
    ? `stage-group-${selected}`
    : "stage-group-dimmed";
}
