import { snapshotGraph } from "../src/topology.ts";

function assert(condition: boolean, message: string): void {
  if (!condition) throw new Error(message);
}

Deno.test("topology: snapshot includes only registered engine stages and boundaries", () => {
  const ids = snapshotGraph.nodes.map((node) => node.id).sort();
  const registered = [
    "__start__",
    "__end__",
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
    "gatekeeper",
    "final_review",
    "intake_draft",
    "requirements_gate",
    "requirements_reopen",
    "arbiter",
    "recovery_admit",
    "recovery_dispatch",
    "recovery_result",
    "proof_refresh",
    "finished_change_review",
  ].sort();
  assert(
    JSON.stringify(ids) === JSON.stringify(registered),
    `Snapshot node set differs from current registered/boundary nodes: ${ids}`,
  );
  assert(
    ids.includes("plan_revision") && ids.includes("plan_blocked"),
    "Review routes missing",
  );
  assert(ids.includes("investigation"), "Investigation missing");
  assert(
    !ids.includes("repair") && !ids.includes("completed") &&
      !ids.includes("failed"),
    "Invented graph node",
  );
});

Deno.test("topology: intake, recovery and independent final review routes are visible", () => {
  const routes = [
    ["__start__", "intake_draft"],
    ["intake_draft", "requirements_gate"],
    ["requirements_gate", "intake_draft"],
    ["requirements_gate", "roadmap"],
    ["requirements_reopen", "intake_draft"],
    ["roadmap", "requirements_reopen"],
    ["worker", "arbiter"],
    ["arbiter", "recovery_admit"],
    ["recovery_admit", "recovery_dispatch"],
    ["recovery_dispatch", "worker"],
    ["worker", "recovery_result"],
    ["recovery_result", "arbiter"],
    ["gatekeeper", "proof_refresh"],
    ["proof_refresh", "finished_change_review"],
    ["finished_change_review", "requirements_reopen"],
    ["finished_change_review", "arbiter"],
    ["finished_change_review", "phase_complete"],
  ];
  for (const [source, target] of routes) {
    assert(
      snapshotGraph.edges.some((edge) =>
        edge.source === source && edge.target === target
      ),
      `${source} to ${target} missing`,
    );
  }
  assert(
    snapshotGraph.graphVersion.includes("0.2.43"),
    "Outdated source snapshot label",
  );
});

Deno.test("topology: Python registered node set matches the viewer", async () => {
  const source = await Deno.readTextFile(
    new URL("../../council/graph.py", import.meta.url),
  );
  const registration = source.slice(
    source.indexOf("for name, operation in ["),
    source.indexOf("graph.add_node(name"),
  );
  const registered = [...registration.matchAll(/\('([a-z_]+)',/g)].map((
    match,
  ) => match[1]);
  const expected = [...registered, "__start__", "__end__"].sort();
  assert(registered.length > 20, "Could not read Python graph registrations");
  assert(
    JSON.stringify(snapshotGraph.nodes.map((node) => node.id).sort()) ===
      JSON.stringify(expected),
    "Engine registrations drifted from viewer",
  );
  const ids = new Set(expected);
  const routes = new Set<string>();
  for (const edge of snapshotGraph.edges) {
    assert(
      ids.has(edge.source) && ids.has(edge.target),
      "Unknown route endpoint",
    );
    const key = `${edge.source}->${edge.target}`;
    assert(!routes.has(key), `Duplicate route ${key}`);
    routes.add(key);
  }
});

Deno.test("topology: observed handoff is an allowed route", () => {
  assert(
    snapshotGraph.edges.some((edge) =>
      edge.source === "architect" && edge.target === "plan_review"
    ),
    "Architect to Plan review route missing",
  );
});

Deno.test("topology: failure routes are conditional for every stage", () => {
  for (
    const edge of snapshotGraph.edges.filter((entry) =>
      entry.label === "failed"
    )
  ) {
    assert(
      edge.kind === "conditional",
      `Dormant failure route visible: ${edge.source}`,
    );
  }
});

Deno.test("topology: phased and legacy Council routes are visible", () => {
  const ids = new Set(snapshotGraph.nodes.map((node) => node.id));
  for (
    const id of [
      "roadmap",
      "roadmap_review",
      "strategy_reset",
      "phase_complete",
    ]
  ) {
    assert(ids.has(id), `${id} stage missing`);
  }
  const routes = [
    ["__start__", "roadmap"],
    ["__start__", "architect"],
    ["roadmap", "roadmap_review"],
    ["roadmap_review", "roadmap"],
    ["roadmap_review", "architect"],
    ["roadmap_review", "plan_blocked"],
    ["roadmap_review", "governor"],
    ["governor", "architect"],
    ["governor", "plan_blocked"],
    ["governor", "gatekeeper"],
    ["plan_review", "governor"],
    ["plan_revision", "governor"],
    ["strategy_reset", "governor"],
    ["phase_complete", "governor"],
    ["plan_review", "strategy_reset"],
    ["strategy_reset", "plan_review"],
    ["plan_blocked", "roadmap"],
    ["prover", "phase_complete"],
    ["prover", "gatekeeper"],
    ["phase_complete", "architect"],
    ["phase_complete", "gatekeeper"],
  ];
  for (const [source, target] of routes) {
    assert(
      snapshotGraph.edges.some((edge) =>
        edge.source === source && edge.target === target
      ),
      `${source} to ${target} route missing`,
    );
  }
});
