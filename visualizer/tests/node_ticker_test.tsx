import { act } from "react";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";
import NodeTicker from "../src/NodeTicker.tsx";
import { useNodeNarrations } from "../src/narrations.ts";

Deno.test("ticker: downward replacement keeps the full accessible blurb and expires old text", async () => {
  const dom = new JSDOM("<div id='root'></div>");
  const saved = new Map<string, PropertyDescriptor | undefined>();
  const timers = new Map<number, () => void>();
  let id = 0;
  for (
    const [key, value] of Object.entries({
      window: dom.window,
      document: dom.window.document,
      IS_REACT_ACT_ENVIRONMENT: true,
      setTimeout: (callback: () => void) => {
        timers.set(++id, callback);
        return id;
      },
      clearTimeout: (id: number) => timers.delete(id),
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
  const render = async (message: string, animate = true, stale = false) => {
    await act(() =>
      root.render(
        <NodeTicker {...{ message, animate, stale }} source="Activity" />,
      )
    );
  };
  try {
    await render("Implementing the readiness fixture.");
    await render("The coding turn returned. Verification is pending.");
    if (
      host.querySelector(".node-ticker-outgoing")?.textContent !==
        "Implementing the readiness fixture."
    ) throw new Error("Previous blurb must move down");
    if (
      host.querySelector(".node-ticker-current")?.textContent !==
        "The coding turn returned. Verification is pending."
    ) throw new Error("New blurb missing");
    const expiry = [...timers.values()][0];
    await render("The coding turn returned. Verification is pending.");
    if ([...timers.values()][0] !== expiry) {
      throw new Error("Unrelated refresh cancelled expiry");
    }
    await act(() => {
      timers.clear();
      expiry();
    });
    if (host.querySelector(".node-ticker-outgoing")) {
      throw new Error("Old text stayed visible");
    }
    await render("A verification command failed.", false, true);
    if (
      host.querySelector('[aria-live="off"]') === null ||
      !host.textContent?.includes("Last observed")
    ) throw new Error("Stopped observations must be qualified");
    if (
      host.querySelector(".node-ticker")?.getAttribute("title") !==
        "A verification command failed."
    ) throw new Error("Full blurb is inaccessible");
  } finally {
    await act(() => root.unmount());
    dom.window.close();
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else Reflect.deleteProperty(globalThis, key);
    }
  }
});

Deno.test("narration polling: reads SQLite projections, retains last observed text on failure and cancels on unmount", async () => {
  const dom = new JSDOM("<div id='root'></div>");
  const saved = new Map<string, PropertyDescriptor | undefined>();
  const timers = new Map<number, { callback: () => void; ms: number }>();
  let id = 0, calls = 0;
  let signal: AbortSignal | undefined;
  const stamp = "2026-10-26T16:00:00+00:00";
  const item = {
    position: 1,
    source_event_id: "a".repeat(64),
    visit_id: "a".repeat(64),
    stage: "worker",
    source_position: 1,
    session_generation: 1,
    source_timestamp: stamp,
    visit_started_at: stamp,
    message: "Working on the readiness fixture.",
    method: "model",
    status: "succeeded",
  };
  const fetcher: typeof fetch = (input, options) => {
    calls++;
    signal = options?.signal ?? undefined;
    if (!String(input).includes("/run/narrations?after=")) {
      throw new Error("Wrong narration endpoint");
    }
    return Promise.resolve(
      new Response(JSON.stringify(
        calls === 1
          ? { version: 1, status: "available", items: [item], next_cursor: 1 }
          : { version: 1, status: "unavailable" },
      )),
    );
  };
  for (
    const [key, value] of Object.entries({
      window: dom.window,
      document: dom.window.document,
      IS_REACT_ACT_ENVIRONMENT: true,
      fetch: fetcher,
      setTimeout: (callback: () => void, ms: number) => {
        timers.set(++id, { callback, ms });
        return id;
      },
      clearTimeout: (id: number) => timers.delete(id),
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
  let observed: ReturnType<typeof useNodeNarrations> | undefined;
  function Probe() {
    observed = useNodeNarrations("run");
    return null;
  }
  try {
    await act(async () => {
      root.render(<Probe />);
      await Promise.resolve();
    });
    if (
      observed?.items[0]?.message !== item.message ||
      observed.status !== "available"
    ) throw new Error("Persisted narration was not loaded");
    const next = [...timers.entries()].find(([, timer]) => timer.ms === 2000)!;
    await act(async () => {
      timers.delete(next[0]);
      next[1].callback();
      await Promise.resolve();
    });
    if (
      observed?.items.length !== 1 || String(observed.status) !== "unavailable"
    ) throw new Error("Failure must retain qualified last-observed narration");
    await act(() => root.unmount());
    if (!signal?.aborted || timers.size) {
      throw new Error("Polling leaked after unmount");
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
