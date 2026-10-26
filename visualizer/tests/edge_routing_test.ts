import { nodeHeight, nodeWidth, routeGraph } from "../src/edgeRouting.ts";
import { snapshotGraph } from "../src/topology.ts";
function assertRoutes(expandedNode?: string) {
  const routes = routeGraph(snapshotGraph, expandedNode);
  for (const edge of snapshotGraph.edges) {
    const route = routes.get(`${edge.source}->${edge.target}`)!;
    if (!route || route.points.length < 2) throw new Error("Missing route");
    const source = snapshotGraph.nodes.find((n) => n.id === edge.source)!;
    const target = snapshotGraph.nodes.find((n) => n.id === edge.target)!;
    if (
      route.points[0].x !== source.x + nodeWidth(source, expandedNode) ||
      route.points[0].y !== source.y + nodeHeight(source, expandedNode) / 2 ||
      route.points.at(-1)!.x !== target.x ||
      route.points.at(-1)!.y !== target.y + nodeHeight(target, expandedNode) / 2
    ) throw new Error("Route detached from node ports");
    for (let i = 1; i < route.points.length; i++) {
      const a = route.points[i - 1], b = route.points[i];
      if (a.x !== b.x && a.y !== b.y) throw new Error("Non-orthogonal segment");
      for (const node of snapshotGraph.nodes) {
        const left = node.x,
          right = node.x + nodeWidth(node, expandedNode),
          top = node.y,
          bottom = node.y + nodeHeight(node, expandedNode);
        const crosses = a.y === b.y
          ? a.y > top && a.y < bottom && Math.max(a.x, b.x) > left &&
            Math.min(a.x, b.x) < right
          : a.x > left && a.x < right && Math.max(a.y, b.y) > top &&
            Math.min(a.y, b.y) < bottom;
        if (crosses) {
          throw new Error(`${edge.source}->${edge.target} crosses ${node.id}`);
        }
      }
    }
  }
  const forward = routes.get("intake_draft->requirements_gate")!.path;
  const reverse = routes.get("requirements_gate->intake_draft")!.path;
  if (forward === reverse) throw new Error("Opposing routes coincide");
  if (routes.get("roadmap->roadmap")!.points.length < 4) {
    throw new Error("Self-loop is invisible");
  }
  if (
    routes.get("phase_complete->architect")!.path ===
      routes.get("phase_complete->governor")!.path
  ) throw new Error("Phase returns coincide");
}

Deno.test("routing: stages without a ticker use compact dimensions", () => {
  const worker = snapshotGraph.nodes.find((node) => node.id === "worker")!;
  if (
    !Object.is(nodeWidth(worker), 150) || !Object.is(nodeHeight(worker), 96)
  ) throw new Error("Non-current nodes must use compact dimensions");
});

Deno.test("routing: paths avoid node interiors and opposing routes use separate lanes", () =>
  assertRoutes());

Deno.test("routing: only the current stage expands and every transition keeps edges attached", () => {
  for (
    const current of snapshotGraph.nodes.filter((node) =>
      node.kind !== "boundary"
    )
  ) {
    for (
      const node of snapshotGraph.nodes.filter((node) =>
        node.kind !== "boundary"
      )
    ) {
      if (
        nodeWidth(node, current.id) !== (node.id === current.id ? 190 : 150) ||
        nodeHeight(node, current.id) !== (node.id === current.id ? 164 : 96)
      ) throw new Error("More than the current node expanded");
    }
    assertRoutes(current.id);
  }
});
