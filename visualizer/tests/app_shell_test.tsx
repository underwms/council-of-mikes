import { renderToStaticMarkup } from "react-dom/server";
import { JSDOM } from "jsdom";
import App from "../src/App.tsx";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { snapshotGraph } from "../src/topology.ts";
import { graphGroups } from "../src/graphGroups.ts";

Deno.test("app shell: graph identity and delivery status are separate from live observations", () => {
  const previous = Object.getOwnPropertyDescriptor(globalThis, "window");
  try {
    for (const [query, live] of [["", false], ["?run=run", true]] as const) {
      const dom = new JSDOM("<!doctype html>", {
        url: `http://127.0.0.1/${query}`,
      });
      Object.defineProperty(globalThis, "window", {
        value: dom.window,
        configurable: true,
      });
      try {
        const html = renderToStaticMarkup(<App />);
        const layout = new JSDOM(html).window.document;
        const graph = layout.querySelector('[aria-label="Execution graph"]')!;
        if (graph.closest("details")) {
          throw new Error("Graph must stay expanded");
        }
        const activity = layout.querySelector<HTMLDetailsElement>(
          ".activity-accordion",
        );
        if (
          live &&
          (!activity || graph.nextElementSibling !== activity || !activity.open)
        ) {
          throw new Error(
            "Expanded Activity explained must be directly beneath the graph",
          );
        }
        for (
          const selector of [
            ".inspector",
            ".playback",
            ".run-information",
            ".delivery-strip",
          ]
        ) {
          const panel = layout.querySelector(selector);
          if (
            panel?.tagName !== "DETAILS" || (panel as HTMLDetailsElement).open
          ) {
            throw new Error(`Panel must start collapsed: ${selector}`);
          }
        }
        if (
          live &&
          layout.querySelector(".observations-accordion")?.hasAttribute("open")
        ) {
          throw new Error("Run summary must start collapsed");
        }
        for (
          const label of [
            "COUNCIL 0.2.43 SOURCE SNAPSHOT",
            "Requirements",
            "Recovery",
            "Final checks",
            "Show all conditional routes",
            "Functional completion:",
            "PR ready:",
          ]
        ) {
          if (!html.includes(label)) {
            throw new Error(`Missing shell behavior: ${label}`);
          }
        }
        if (html.includes("What’s happening") !== live) {
          throw new Error("Live observations leaked into replay");
        }
        if (
          !html.includes(
            live ? "Last reported delivery" : "Delivery at selected event",
          )
        ) throw new Error("Delivery time basis unclear");
      } finally {
        dom.window.close();
      }
    }
  } finally {
    if (previous) Object.defineProperty(globalThis, "window", previous);
    else Reflect.deleteProperty(globalThis, "window");
  }
});

Deno.test("app shell: group clicks shade all matching graph nodes and clear the shading", async () => {
  const dom = new JSDOM("<div id='root'></div>", {
    url: "http://127.0.0.1/",
    pretendToBeVisual: true,
  });
  const saved = new Map<string, PropertyDescriptor | undefined>();
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  const recording = await Deno.readTextFile(
    new URL("../public/sample-events.jsonl", import.meta.url),
  );
  for (
    const [key, value] of Object.entries({
      window: dom.window,
      document: dom.window.document,
      HTMLElement: dom.window.HTMLElement,
      Element: dom.window.Element,
      Node: dom.window.Node,
      getComputedStyle: dom.window.getComputedStyle.bind(dom.window),
      ResizeObserver: ResizeObserverStub,
      requestAnimationFrame: dom.window.requestAnimationFrame.bind(dom.window),
      cancelAnimationFrame: dom.window.cancelAnimationFrame.bind(dom.window),
      IS_REACT_ACT_ENVIRONMENT: true,
      fetch: () => Promise.resolve(new Response(recording)),
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
  let navigations = 0;
  dom.window.HTMLElement.prototype.scrollTo = () => {
    navigations++;
  };
  try {
    await act(async () => {
      root.render(<App />);
    });
    const assertGraphVisible = () => {
      const nodes = [
        ...host.querySelectorAll<HTMLElement>(".react-flow__node"),
      ];
      if (
        nodes.length !== snapshotGraph.nodes.length ||
        nodes.some((node) => node.style.visibility === "hidden")
      ) {
        throw new Error(
          "Graph nodes disappeared while waiting for browser measurements",
        );
      }
    };
    assertGraphVisible();
    for (const group of graphGroups) {
      const button = [...host.querySelectorAll("button")].find((entry) =>
        entry.textContent === group.label
      )!;
      await act(async () => button.click());
      assertGraphVisible();
      const highlighted = [
        ...host.querySelectorAll(`.react-flow__node.stage-group-${group.id}`),
      ];
      if (
        highlighted.length !== group.nodes.length ||
        highlighted.some((node) =>
          !group.nodes.includes((node as HTMLElement).dataset.id!)
        )
      ) {
        throw new Error(
          `Incorrect highlighted nodes for ${group.id}: ${highlighted.length}`,
        );
      }
      if (button.getAttribute("aria-pressed") !== "true") {
        throw new Error("Button not pressed");
      }
      await act(async () => button.click());
      if (host.querySelector('.react-flow__node[class*="stage-group-"]')) {
        throw new Error("Clear retained graph shading");
      }
    }
    const next = [...host.querySelectorAll<HTMLButtonElement>("button")].find(
      (button) => button.textContent === "Next event",
    )!;
    await act(() => next.click());
    assertGraphVisible();
    if (navigations !== 4) throw new Error("Group navigation changed");
  } finally {
    await act(async () => root.unmount());
    dom.window.close();
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else Reflect.deleteProperty(globalThis, key);
    }
  }
});
