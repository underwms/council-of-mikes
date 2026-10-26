import { act } from "react";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";
import Tooltip from "../src/Tooltip.tsx";
import { type Narration, tickerForNode } from "../src/narrations.ts";
import { parseRecording } from "../src/contracts.ts";
import { projectAt } from "../src/reducer.ts";
const stamp = "2026-10-26T18:00:00+00:00";
const events = parseRecording(
  [
    { event: "node_started", stage: "intake_draft" },
    { event: "node_finished", stage: "intake_draft" },
    { event: "node_started", stage: "requirements_gate" },
    { event: "approval_waiting", stage: "requirements_gate" },
  ].map((e, i) =>
    JSON.stringify({
      run_id: "run",
      timestamp: stamp,
      elapsed_seconds: i,
      ...e,
    })
  ).join("\n"),
);
const narration: Narration = {
  position: 1,
  source_event_id: "a".repeat(64),
  visit_id: "b".repeat(64),
  stage: "intake_draft",
  session_generation: 1,
  source_position: 1,
  source_timestamp: stamp,
  visit_started_at: stamp,
  message: "Drafting the requirements for your review.",
  method: "model",
  status: "succeeded",
};
Deno.test("ticker display: transition clears the old node even when its narration arrives late", () => {
  if (
    tickerForNode("intake_draft", projectAt(events, 1), [narration])
      ?.message !== narration.message
  ) throw new Error("Current node must display narration");
  const after = projectAt(events, 4);
  if (tickerForNode("intake_draft", after, [narration])) {
    throw new Error("Transition must clear previous ticker");
  }
  if (!tickerForNode("requirements_gate", after, [])) {
    throw new Error("Waiting destination must keep its ticker");
  }
  if (tickerForNode("intake_draft", projectAt(events, 0), [narration])) {
    throw new Error("Restart must clear ticker");
  }
});
Deno.test("tooltip: blue summary is exactly the shared ticker message and clears after transition", async () => {
  const dom = new JSDOM(
    "<div id='root'></div><button id='anchor'>Draft</button>",
  );
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
  const root = createRoot(dom.window.document.getElementById("root")!);
  const target = {
    nodeId: "intake_draft",
    element: dom.window.document.getElementById("anchor")!,
  };
  const render = async (position: number) => {
    const state = projectAt(events, position);
    await act(() =>
      root.render(
        <Tooltip
          target={target}
          state={state}
          context={{ mode: "live", connected: true, atEnd: false }}
          tickerMessage={tickerForNode(target.nodeId, state, [narration])
            ?.message}
          onMouseEnter={() => {}}
          onMouseLeave={() => {}}
        />,
      )
    );
  };
  try {
    await render(1);
    if (
      dom.window.document.querySelector(".node-tooltip-summary")
        ?.textContent !== narration.message
    ) throw new Error("Popup disagrees with node ticker");
    await render(4);
    if (dom.window.document.querySelector(".node-tooltip-summary")) {
      throw new Error("Popup retained stale ticker text");
    }
  } finally {
    await act(() => root.unmount());
    dom.window.close();
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else Reflect.deleteProperty(globalThis, key);
    }
  }
});
