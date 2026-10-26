import { act } from "react";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";
import { useEdgeMotion } from "../src/useEdgeMotion.ts";
import type { Transition } from "../src/graphProgress.ts";

Deno.test("motion: later calls preserve expiry; seek, resume, replacement and disconnect clear motion", async () => {
  const dom = new JSDOM("<div id='root'></div>");
  const saved = new Map<string, PropertyDescriptor | undefined>();
  const timers = new Map<number, () => void>();
  let timerId = 0;
  for (
    const [key, value] of Object.entries({
      window: dom.window,
      document: dom.window.document,
      IS_REACT_ACT_ENVIRONMENT: true,
      setTimeout: (callback: () => void) => {
        timers.set(++timerId, callback);
        return timerId;
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
  let motion: Transition | null = null;
  const transition = {
    source: "requirements_gate",
    target: "roadmap",
    cursor: "3",
    position: 3,
  };
  function Probe(
    { position, enabled, latest, identity }: {
      position: number;
      enabled: boolean;
      latest: Transition | undefined;
      identity: string;
    },
  ) {
    motion = useEdgeMotion(latest, position, enabled, identity);
    return null;
  }
  const render = async (
    position: number,
    enabled = true,
    latest: Transition | undefined = transition,
    identity = "recording",
  ) => {
    await act(() => {
      root.render(<Probe {...{ position, enabled, latest, identity }} />);
    });
  };
  try {
    await render(2);
    await render(3);
    if (!motion) throw new Error("Approval handoff should animate");
    const expiry = [...timers.values()][0];
    await render(4, true, { ...transition });
    if ([...timers.values()][0] !== expiry) {
      throw new Error("Call event replaced motion expiry");
    }
    await act(() => {
      timers.clear();
      expiry();
    });
    if (motion) throw new Error("Traveller stuck after expiry");
    await render(2);
    await render(3);
    await render(4, false);
    if (motion) {
      throw new Error("Disconnected/waiting observation must clear motion");
    }
    await render(2);
    await render(3);
    await render(2);
    if (motion) throw new Error("Rewind must clear motion");
    await render(3);
    await render(4, true, transition, "replacement");
    if (motion) throw new Error("Recording replacement must clear motion");
    const loop = {
      source: "roadmap",
      target: "roadmap",
      cursor: "5",
      position: 5,
    };
    await render(7, true, loop, "replacement");
    if (!motion) throw new Error("Batched self-loop handoff should animate");
    await render(8, true, undefined, "replacement");
    // Pass undefined through JSX directly: render's default is intentionally a normal handoff.
    await act(() =>
      root.render(
        <Probe
          position={9}
          enabled
          latest={undefined}
          identity="replacement"
        />,
      )
    );
    if (motion) {
      throw new Error("Resume without a transition must clear old motion");
    }
    await render(2);
    await render(3);
    await act(() => root.unmount());
    if (timers.size) throw new Error("Unmount leaked expiry timer");
  } finally {
    await act(() => root.unmount());
    dom.window.close();
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else Reflect.deleteProperty(globalThis, key);
    }
  }
});
