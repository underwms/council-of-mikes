import { renderToStaticMarkup } from "react-dom/server";
import { Position } from "@xyflow/react";
import GraphEdge from "../src/GraphEdge.tsx";
Deno.test("edge renderer: unused routes have no gradient or traveller; motion follows routed geometry", () => {
  const props = {
    id: "requirements_gate->roadmap",
    source: "requirements_gate",
    target: "roadmap",
    sourceX: 670,
    sourceY: 152,
    targetX: 750,
    targetY: 152,
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
    style: { strokeWidth: 2 },
  };
  const unused = renderToStaticMarkup(
    <svg>
      <GraphEdge {...props} />
    </svg>,
  );
  if (unused.includes("linearGradient") || unused.includes("animateMotion")) {
    throw new Error("Unused route shows activity");
  }
  const visited = renderToStaticMarkup(
    <svg>
      <GraphEdge
        {...props}
        data={{ gradientStart: "#59b9c9", gradientEnd: "#006d83" }}
      />
    </svg>,
  );
  if (
    !visited.includes("linearGradient") || visited.includes("animateMotion")
  ) throw new Error("History must show only its gradient");
  const moving = renderToStaticMarkup(
    <svg>
      <GraphEdge
        {...props}
        data={{
          moving: true,
          routePath: "M 670,152 L 750,152",
          motionKey: "handoff",
          gradientStart: "#59b9c9",
          gradientEnd: "#006d83",
        }}
      />
    </svg>,
  );
  if (
    !moving.includes("animateMotion") ||
    !moving.includes('path="M 670,152 L 750,152"')
  ) throw new Error("Traveller must follow the actual approval path");
});
