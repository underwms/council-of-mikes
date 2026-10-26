import { act } from "react";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";
import ObservationPanel from "../src/ObservationPanel.tsx";

function assert(value: unknown, message: string): asserts value {
  if (!value) throw new Error(message);
}
async function interact(action: () => void) {
  await act(async () => {
    action();
    await Promise.resolve();
  });
}
const summary = (message: string) => ({
  version: 1,
  run_id: "run",
  current: { state: "recorded_activity", message },
  coverage: "prospective_events_only",
  groups: [{
    value: "coder",
    attempts: 1,
    usage: { reported_input_tokens: 12 },
  }],
});
const item = (position: number, event = "recovery_dispatched") => ({
  position,
  event,
  stage: "recovery_dispatch",
  session_id: "session",
  session_generation: 1,
  source_seq: position,
  event_id: "a".repeat(64),
  timestamp: "2026-10-25T12:00:00Z",
  explanation: {
    state: "recovering",
    message: "An admitted repair was dispatched.",
  },
  accounting: {
    requested_model: "requested",
    returned_model: "reported",
    usage: { input_tokens: 12 },
  },
  measurement: {
    execution_id: "b".repeat(64),
    duration_seconds: 0,
    completion: "completed",
  },
  functional_complete: true,
  pr_ready: false,
});

async function withDom(
  fetcher: typeof fetch,
  action: (host: HTMLElement, render: () => Promise<void>) => Promise<void>,
) {
  const dom = new JSDOM("<!doctype html><div id='root'></div>", {
    url: "http://127.0.0.1/",
  });
  const saved = new Map<string, PropertyDescriptor | undefined>();
  for (
    const [key, value] of Object.entries({
      window: dom.window,
      document: dom.window.document,
      HTMLElement: dom.window.HTMLElement,
      IS_REACT_ACT_ENVIRONMENT: true,
      fetch: fetcher,
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
  try {
    await action(host, () =>
      interact(() => {
        root.render(<ObservationPanel runId="run" connected />);
      }));
  } finally {
    await interact(() => root.unmount());
    dom.window.close();
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else Reflect.deleteProperty(globalThis, key);
    }
  }
}
function button(host: HTMLElement, label: string): HTMLButtonElement {
  const found = [...host.querySelectorAll("button")].find((entry) =>
    entry.textContent === label
  );
  assert(found, `Missing button: ${label}`);
  return found;
}

Deno.test("observation DOM: readable explanations stay visible while diagnostics start collapsed", async () => {
  await withDom((input) =>
    Promise.resolve(Response.json(
      String(input).includes("summary")
        ? summary("Waiting for your requirements approval.")
        : {
          version: 1,
          items: [item(1), { ...item(2, "node_started"), explanation: null }],
          next_cursor: 2,
        },
    )), async (host, render) => {
    await render();
    const heading = [...host.querySelectorAll("h2")].find((entry) =>
      entry.textContent === "Waiting for your requirements approval."
    );
    assert(
      heading &&
        heading.closest(".observations-accordion")?.tagName === "DETAILS" &&
        !(heading.closest(".observations-accordion") as HTMLDetailsElement)
          .open,
      "Run summary should be in the collapsed accordion",
    );
    const event = host.querySelector(".observation-events > li")!;
    const explanation = [...event.querySelectorAll("p")].find((entry) =>
      entry.textContent === "An admitted repair was dispatched."
    );
    assert(
      explanation && explanation.closest("details")?.open,
      "Readable event should start in the expanded activity accordion",
    );
    const metrics = event.querySelector("dl");
    assert(
      metrics?.closest("details") && !metrics.closest("details")!.open,
      "Event metrics expanded",
    );
    const usage = [...host.querySelectorAll("h3")].find((entry) =>
      entry.textContent === "Reported usage"
    );
    assert(
      usage?.closest("details") && !usage.closest("details")!.open,
      "Usage expanded",
    );
    assert(
      host.querySelectorAll(".observation-events > li")[1].querySelector(
        ".activity-explanation",
      )?.textContent?.trim(),
      "Missing fallback explanation",
    );
    assert(
      host.textContent?.includes("What’s happening"),
      "Activity section label",
    );
    const activity = host.querySelector<HTMLDetailsElement>(
      ".activity-accordion",
    )!;
    assert(
      activity === host.firstElementChild && activity.open,
      "Activity is not first and expanded",
    );
    await interact(() => activity.querySelector("summary")!.click());
    assert(!activity.open, "Activity cannot be collapsed");
    await interact(() => activity.querySelector("summary")!.click());
    assert(activity.open, "Activity cannot be expanded");
    assert(
      host.querySelectorAll(".observation-events > li").length === 2,
      "Accordion toggle lost events",
    );
  });
});

Deno.test("observation DOM: activity polls new events automatically and retains history", async () => {
  const originalTimer = globalThis.setTimeout;
  const scheduled: (() => void)[] = [];
  globalThis.setTimeout = ((callback: () => void, delay?: number) => {
    if (delay === 5000) {
      scheduled.push(callback);
      return 0;
    }
    return originalTimer(callback, delay);
  }) as typeof globalThis.setTimeout;
  const requested: string[] = [];
  try {
    await withDom((input) => {
      const url = String(input);
      requested.push(url);
      const cursor = Number(
        new URL(url, "http://127.0.0.1").searchParams.get("after"),
      );
      return Promise.resolve(
        Response.json(
          url.includes("summary") ? summary("Current activity") : {
            version: 1,
            items: [item(cursor + 1)],
            next_cursor: cursor + 1,
          },
        ),
      );
    }, async (host, render) => {
      await render();
      await interact(() =>
        scheduled.splice(0).forEach((callback) => callback())
      );
      assert(
        requested.some((url) => url.includes("/milestones?after=1")),
        "Feed does not poll its next cursor",
      );
      assert(
        host.querySelectorAll(".observation-events > li").length === 2,
        "Automatic update lost history",
      );
    });
  } finally {
    globalThis.setTimeout = originalTimer;
  }
});

Deno.test("observation DOM: mount, pagination, stream switching and refresh work together", async () => {
  let calls = 0;
  const requested: string[] = [];
  await withDom((input) => {
    const url = String(input);
    requested.push(url);
    if (url.includes("summary")) {
      return Promise.resolve(
        Response.json(summary(`Progress revision ${++calls}`)),
      );
    }
    const cursor = Number(
      new URL(url, "http://127.0.0.1").searchParams.get("after"),
    );
    return Promise.resolve(
      Response.json({
        version: 1,
        items: cursor < 2 ? [item(cursor + 1)] : [],
        next_cursor: Math.min(cursor + 1, 2),
      }),
    );
  }, async (host, render) => {
    await render();
    assert(
      host.textContent?.includes("Progress revision 1"),
      "Initial summary not rendered",
    );
    assert(
      host.textContent?.includes("An admitted repair was dispatched."),
      "Milestone explanation missing",
    );
    assert(
      host.textContent?.includes("Functional completion: Yes · PR ready: No"),
      "Delivery flags conflated",
    );
    assert(
      host.textContent?.includes("requested") &&
        host.textContent.includes("reported"),
      "Model identities missing",
    );
    await interact(() => button(host, "Load next / check for new").click());
    assert(
      host.querySelectorAll(".observation-events > li").length === 2,
      "Page not appended",
    );
    await interact(() => button(host, "Load next / check for new").click());
    assert(
      host.textContent?.includes("No further observations"),
      "Empty page not explained",
    );
    await interact(() => button(host, "First page").click());
    assert(
      host.querySelectorAll(".observation-events > li").length === 1,
      "Reset did not clear history",
    );
    const selects = host.querySelectorAll("select");
    await interact(() => {
      selects[1].value = "commands";
      selects[1].dispatchEvent(
        new host.ownerDocument.defaultView!.Event("change", { bubbles: true }),
      );
    });
    assert(
      requested.some((url) => url.includes("/commands?after=0")),
      "Stream switch reused cursor",
    );
    await interact(() => {
      selects[0].value = "reported_model";
      selects[0].dispatchEvent(
        new host.ownerDocument.defaultView!.Event("change", { bubbles: true }),
      );
    });
    assert(
      requested.some((url) => url.includes("group_by=reported_model")),
      "Grouping not applied",
    );
    await interact(() => button(host, "Refresh summary").click());
    assert(
      host.textContent?.includes("Progress revision 3"),
      "Manual refresh not applied",
    );
  });
});

Deno.test("observation DOM: superseded requests are aborted and cannot overwrite new selection", async () => {
  let resolveOld: ((value: Response) => void) | undefined;
  let oldSignal: AbortSignal | undefined;
  await withDom((input, options) => {
    if (String(input).includes("group_by=role")) {
      oldSignal = options?.signal ?? undefined;
      return new Promise((resolve) => {
        resolveOld = resolve;
      });
    }
    if (String(input).includes("summary")) {
      return Promise.resolve(Response.json(summary("New selection")));
    }
    return Promise.resolve(
      Response.json({ version: 1, items: [], next_cursor: 0 }),
    );
  }, async (host, render) => {
    await render();
    const select = host.querySelector("select")!;
    await interact(() => {
      select.value = "provider";
      select.dispatchEvent(
        new host.ownerDocument.defaultView!.Event("change", { bubbles: true }),
      );
    });
    assert(oldSignal?.aborted, "Old selection not aborted");
    await interact(() => {
      resolveOld!(Response.json(summary("OBSOLETE")));
    });
    assert(
      host.textContent?.includes("New selection") &&
        !host.textContent.includes("OBSOLETE"),
      "Old response replaced current selection",
    );
  });
});

Deno.test("observation DOM: failed summary and unsupported detail store remain explicit", async () => {
  await withDom(
    (input) =>
      Promise.resolve(
        String(input).includes("summary")
          ? new Response("unavailable", { status: 503 })
          : Response.json({ version: 1, status: "unsupported_schema" }),
      ),
    async (host, render) => {
      await render();
      assert(
        host.textContent?.includes(
          "Observations unavailable: Observation request failed (HTTP 503)",
        ),
        "HTTP failure concealed",
      );
      assert(
        host.textContent?.includes("Details unavailable: unsupported schema"),
        "Storage schema failure concealed",
      );
      assert(
        button(host, "Load next / check for new").disabled,
        "Unavailable pages can paginate",
      );
    },
  );
});

Deno.test("observation DOM: export downloads only the current typed page", async () => {
  const originalCreate = URL.createObjectURL,
    originalRevoke = URL.revokeObjectURL;
  const originalTimer = globalThis.setTimeout;
  let captured: Blob | undefined;
  let revoked = false;
  let filename = "";
  URL.createObjectURL = (blob) => {
    assert(blob instanceof Blob, "Download must be a JSON Blob");
    captured = blob;
    return originalCreate(blob);
  };
  URL.revokeObjectURL = (url) => {
    revoked = true;
    originalRevoke(url);
  };
  globalThis.setTimeout = ((callback: () => void, delay?: number) => {
    if (delay === 1000) {
      callback();
      return 0;
    }
    return originalTimer(callback, delay);
  }) as typeof globalThis.setTimeout;
  try {
    await withDom(
      (input) =>
        Promise.resolve(Response.json(
          String(input).includes("summary")
            ? summary("Ready for inspection")
            : {
              version: 1,
              items: [{ ...item(1), prompt: "PRIVATE" }],
              next_cursor: 1,
            },
        )),
      async (host, render) => {
        const prototype =
          host.ownerDocument.defaultView!.HTMLAnchorElement.prototype;
        const click = prototype.click;
        prototype.click = function () {
          filename = this.download;
        };
        try {
          await render();
          await interact(() => button(host, "Export this page").click());
          assert(captured, "No page download created");
          const exported = await captured.text();
          const parsed = JSON.parse(exported);
          assert(
            parsed.run_id === "run" && parsed.next_cursor === 1 &&
              parsed.items.length === 1,
            "Export lost page/run identity",
          );
          assert(
            !exported.includes("PRIVATE"),
            "Export leaked discarded payload",
          );
          assert(
            filename === "council-run-milestones-1.json" && revoked,
            "Download name or URL cleanup incorrect",
          );
        } finally {
          prototype.click = click;
        }
      },
    );
  } finally {
    URL.createObjectURL = originalCreate;
    URL.revokeObjectURL = originalRevoke;
    globalThis.setTimeout = originalTimer;
  }
});

Deno.test("observation DOM: failed next page retains history with an explicit stale notice", async () => {
  await withDom((input) => {
    const url = String(input);
    return Promise.resolve(
      url.includes("summary")
        ? Response.json(summary("Last observed progress"))
        : url.includes("after=1")
        ? new Response("failed", { status: 503 })
        : Response.json({ version: 1, items: [item(1)], next_cursor: 1 }),
    );
  }, async (host, render) => {
    await render();
    await interact(() => button(host, "Load next / check for new").click());
    assert(
      host.querySelectorAll(".observation-events > li").length === 1,
      "Failed page destroyed prior observations",
    );
    assert(
      host.textContent?.includes("Details unavailable") &&
        host.textContent.includes("last observed"),
      "Stale details not qualified",
    );
    assert(
      button(host, "Export this page").disabled,
      "Failed page can be exported as current",
    );
  });
});
