import { graphCanvas } from "../src/graphLayout.ts";
import { nodeHeight, nodeWidth } from "../src/edgeRouting.ts";
import { snapshotGraph } from "../src/topology.ts";

function assert(condition: boolean, message: string): void {
  if (!condition) throw new Error(message);
}

Deno.test("graph canvas includes the rightmost and lowest stages at a fixed scale", () => {
  const layout = graphCanvas(snapshotGraph);
  assert(layout.scale === 0.82, "scale must stay fixed");
  const rightmost = Math.max(
    ...snapshotGraph.nodes.map((node) => node.x + nodeWidth(node)),
  );
  const lowest = Math.max(
    ...snapshotGraph.nodes.map((node) => node.y + nodeHeight(node)),
  );
  assert(layout.width >= rightmost * layout.scale + 24, "END is clipped");
  assert(
    layout.height >= lowest * layout.scale + 24,
    "lower review row is clipped",
  );
});

Deno.test("graph canvas reserves a lower lane for the next-phase return", () => {
  const loop = snapshotGraph.edges.find((edge) =>
    edge.source === "phase_complete" && edge.target === "architect"
  );
  assert(loop?.kind === "phase-loop", "Next-phase edge needs its loop style");
  const layout = graphCanvas(snapshotGraph);
  assert(
    layout.height >= 700 * layout.scale + 24,
    "Next-phase return would be clipped by the canvas",
  );
});
