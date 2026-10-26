import { nodeHeight, nodeWidth } from "./edgeRouting.ts";
import type { GraphManifest } from "./topology.ts";

export const GRAPH_SCALE = 0.82;
export const PHASE_LOOP_Y = 700;

export function graphCanvas(graph: GraphManifest) {
  const right = Math.max(
    ...graph.nodes.map((node) => node.x + nodeWidth(node, node.id)),
  );
  const bottom = Math.max(
    ...graph.nodes.map((node) => node.y + nodeHeight(node, node.id)),
    graph.edges.some((edge) => edge.kind === "phase-loop") ? PHASE_LOOP_Y : 0,
  );
  return {
    scale: GRAPH_SCALE,
    width: Math.ceil(right * GRAPH_SCALE + 32),
    height: Math.ceil(bottom * GRAPH_SCALE + 32),
  };
}
