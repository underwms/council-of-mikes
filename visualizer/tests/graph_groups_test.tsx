import * as React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";
import GraphNavigation from "../src/GraphNavigation.tsx";
import {
  graphGroups,
  groupForNode,
  type GroupId,
  groupNodeClass,
} from "../src/graphGroups.ts";
import { snapshotGraph } from "../src/topology.ts";

function assert(value: unknown, message: string): asserts value {
  if (!value) throw new Error(message);
}

Deno.test("graph groups: every stage belongs to exactly one group, boundaries stay neutral", () => {
  for (const node of snapshotGraph.nodes) {
    const groups = graphGroups.filter((group) => group.nodes.includes(node.id));
    assert(groups.length === (node.kind === "boundary" ? 0 : 1), node.id);
    assert(groupForNode(node.id) === groups[0]?.id, `Lookup: ${node.id}`);
  }
  for (const group of graphGroups) {
    for (const id of group.nodes) {
      assert(
        snapshotGraph.nodes.some((node) => node.id === id),
        `Unknown: ${id}`,
      );
      assert(groupNodeClass(id, group.id) === `stage-group-${group.id}`, id);
      assert(groupNodeClass(id, null) === "", "Clear retains a highlight");
    }
  }
  assert(
    groupForNode("requirements_reopen") === "requirements",
    "Scope reopening",
  );
  assert(groupForNode("proof_refresh") === "final", "Proof refresh");
  assert(groupForNode("recovery_result") === "recovery", "Recovery result");
  assert(
    groupNodeClass("worker", "requirements") === "stage-group-dimmed",
    "Unrelated node",
  );
});

Deno.test("graph groups: rendered buttons toggle, switch, clear and navigate", async () => {
  const dom = new JSDOM("<div id='root'></div>");
  const saved = new Map<string, PropertyDescriptor | undefined>();
  for (
    const [key, value] of Object.entries({
      window: dom.window,
      document: dom.window.document,
      IS_REACT_ACT_ENVIRONMENT: true,
    })
  ) {
    saved.set(key, Object.getOwnPropertyDescriptor(globalThis, key));
    Object.defineProperty(globalThis, key, {
      value,
      configurable: true,
      writable: true,
    });
  }
  const host = dom.window.document.getElementById("root")!;
  const root = createRoot(host);
  const navigated: string[] = [];
  function Harness() {
    const [group, setGroup] = React.useState<GroupId | null>(null);
    return (
      <GraphNavigation
        selectedGroup={group}
        onGroupChange={setGroup}
        onNavigate={(id) => navigated.push(id)}
      />
    );
  }
  try {
    await act(async () => root.render(<Harness />));
    const buttons = [...host.querySelectorAll("button")];
    assert(buttons.length === 4, "Four group controls");
    assert(
      buttons.every((button) =>
        button.getAttribute("aria-pressed") === "false"
      ),
      "Initial state",
    );
    for (const [index, expected] of [[0, 1], [1, 1], [2, 1], [3, 1], [3, 0]]) {
      await act(async () => buttons[index].click());
      const pressed = buttons.filter((button) =>
        button.getAttribute("aria-pressed") === "true"
      );
      assert(pressed.length === expected, "Exclusive toggle state");
    }
    assert(
      navigated.join(",") === "intake_draft,roadmap,arbiter,gatekeeper",
      "Navigation on activation only",
    );
  } finally {
    await act(async () => root.unmount());
    dom.window.close();
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else Reflect.deleteProperty(globalThis, key);
    }
  }
});
