import type { GraphManifest, GraphNode } from "./topology.ts";

export const NODE_WIDTH = 190;
export const NODE_HEIGHT = 164;
export const nodeWidth = (node: GraphNode, expandedNode?: string) =>
  node.kind === "boundary" ? 90 : node.id === expandedNode ? NODE_WIDTH : 150;
export const nodeHeight = (node: GraphNode, expandedNode?: string) =>
  node.kind === "boundary" ? 48 : node.id === expandedNode ? NODE_HEIGHT : 96;
export type Point = { x: number; y: number };
export type EdgeRoute = { path: string; points: Point[] };
const key = (a: number, b: number) => a < b ? `${a}:${b}` : `${b}:${a}`;

/** Fixed visibility grid: adding a conditional edge never relocates existing routes. */
export function routeGraph(
  graph: GraphManifest,
  expandedNode?: string,
): Map<string, EdgeRoute> {
  const width = (node: GraphNode) => nodeWidth(node, expandedNode);
  const height = (node: GraphNode) => nodeHeight(node, expandedNode);
  // In close columns, shorten the port stub so it cannot enter a neighboring node.
  const ports = new Map(graph.nodes.map((node) => {
    const y = node.y + height(node) / 2;
    const row = graph.nodes.filter((other) =>
      other.id !== node.id && y > other.y && y < other.y + height(other)
    );
    const right = node.x + width(node);
    const rightGap = Math.min(
      48,
      ...row.filter((other) => other.x >= right).map((other) =>
        other.x - right
      ),
    );
    const leftGap = Math.min(
      48,
      ...row.filter((other) => other.x + width(other) <= node.x).map(
        (other) => node.x - other.x - width(other),
      ),
    );
    return [node.id, {
      exit: right + rightGap / 2,
      entry: node.x - leftGap / 2,
    }];
  }));
  const xs = [
    ...new Set(
      graph.nodes.flatMap(
        (
          n,
        ) => [
          ports.get(n.id)!.entry,
          n.x,
          n.x + width(n),
          ports.get(n.id)!.exit,
        ],
      ),
    ),
  ].sort((a, b) => a - b);
  const ys = [
    ...new Set([
      ...graph.nodes.flatMap(
        (n) => [n.y - 24, n.y + height(n) / 2, n.y + height(n) + 24],
      ),
      700,
      724,
    ]),
  ].sort((a, b) => a - b);
  const points = ys.flatMap((y) => xs.map((x) => ({ x, y })));
  const index = (x: number, y: number) =>
    ys.indexOf(y) * xs.length + xs.indexOf(x);
  const blocked = (a: Point, b: Point) =>
    graph.nodes.some((n) =>
      a.y === b.y
        ? a.y > n.y && a.y < n.y + height(n) && Math.max(a.x, b.x) > n.x &&
          Math.min(a.x, b.x) < n.x + width(n)
        : a.x > n.x && a.x < n.x + width(n) && Math.max(a.y, b.y) > n.y &&
          Math.min(a.y, b.y) < n.y + height(n)
    );
  const neighbors = points.map((a, i) =>
    [i - 1, i + 1, i - xs.length, i + xs.length].filter((j) =>
      j >= 0 && j < points.length &&
      (Math.floor(i / xs.length) === Math.floor(j / xs.length) ||
        i % xs.length === j % xs.length) &&
      !blocked(a, points[j])
    )
  );
  const usage = new Map<string, number>();
  function search(start: number, end: number): number[] {
    const distance = new Map<number, number>([[start, 0]]);
    const parent = new Map<number, number>();
    const heap: { id: number; cost: number }[] = [];
    const heuristic = (id: number) =>
      Math.abs(points[id].x - points[end].x) +
      Math.abs(points[id].y - points[end].y);
    function push(id: number, cost: number) {
      let i = heap.length;
      heap.push({ id, cost });
      while (i > 0) {
        const p = (i - 1) >> 1;
        if (heap[p].cost <= cost) break;
        [heap[p], heap[i]] = [heap[i], heap[p]];
        i = p;
      }
    }
    function pop() {
      const first = heap[0], last = heap.pop()!;
      if (heap.length) {
        heap[0] = last;
        let i = 0;
        while (true) {
          let c = i * 2 + 1;
          if (c >= heap.length) break;
          if (c + 1 < heap.length && heap[c + 1].cost < heap[c].cost) c++;
          if (heap[i].cost <= heap[c].cost) break;
          [heap[i], heap[c]] = [heap[c], heap[i]];
          i = c;
        }
      }
      return first;
    }
    push(start, heuristic(start));
    const closed = new Set<number>();
    while (heap.length) {
      const { id } = pop();
      if (closed.has(id)) continue;
      if (id === end) {
        const result = [end];
        while (result[0] !== start) result.unshift(parent.get(result[0])!);
        return result;
      }
      closed.add(id);
      for (const next of neighbors[id]) {
        const a = points[id], b = points[next];
        const length = Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
        const cost = distance.get(id)! +
          length * (1 + (usage.get(key(id, next)) ?? 0) * 0.7);
        if (cost < (distance.get(next) ?? Infinity)) {
          distance.set(next, cost);
          parent.set(next, id);
          push(next, cost + heuristic(next));
        }
      }
    }
    throw new Error("No obstacle-free graph route");
  }
  const routes = new Map<string, EdgeRoute>();
  let phaseLane = 700;
  // Main routes get first use of short corridors; conditional visibility does not affect routing.
  const ordered = [...graph.edges].sort((a, b) =>
    Number(a.kind === "conditional") - Number(b.kind === "conditional")
  );
  for (const edge of ordered) {
    const source = graph.nodes.find((n) => n.id === edge.source)!;
    const target = graph.nodes.find((n) => n.id === edge.target)!;
    const start = index(
      source.x + width(source),
      source.y + height(source) / 2,
    );
    const end = index(target.x, target.y + height(target) / 2);
    const exit = index(
      ports.get(source.id)!.exit,
      source.y + height(source) / 2,
    );
    const entry = index(
      ports.get(target.id)!.entry,
      target.y + height(target) / 2,
    );
    let middle: number[];
    if (edge.kind === "phase-loop") {
      const via = index(ports.get(source.id)!.exit, phaseLane);
      const viaEnd = index(ports.get(target.id)!.entry, phaseLane);
      middle = [
        ...search(exit, via),
        ...search(via, viaEnd).slice(1),
        ...search(viaEnd, entry).slice(1),
      ];
      phaseLane += 24;
    } else middle = search(exit, entry);
    const ids = [start, ...middle, end];
    for (let i = 1; i < ids.length; i++) {
      usage.set(
        key(ids[i - 1], ids[i]),
        (usage.get(key(ids[i - 1], ids[i])) ?? 0) + 1,
      );
    }
    const simplified = ids.map((id) => points[id]).filter((p, i, list) =>
      i === 0 || i === list.length - 1 ||
      !((list[i - 1].x === p.x && p.x === list[i + 1].x) ||
        (list[i - 1].y === p.y && p.y === list[i + 1].y))
    );
    routes.set(`${edge.source}->${edge.target}`, {
      points: simplified,
      path: simplified.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x},${p.y}`)
        .join(" "),
    });
  }
  return routes;
}
