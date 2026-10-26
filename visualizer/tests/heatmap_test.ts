import { parseRecording } from "../src/contracts.ts";
import { HEAT_COLORS, visitBadgeStyle } from "../src/heatmap.ts";
import { appendLiveEvent } from "../src/live.ts";
import { projectAt } from "../src/reducer.ts";

function assert(condition: boolean, message: string): void {
  if (!condition) throw new Error(message);
}

function luminance(hex: string): number {
  const channels = hex.slice(1).match(/../g)!.map((part) => {
    const value = parseInt(part, 16) / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}

Deno.test("heatmap: every repeat visit makes the badge redder through ten visits", () => {
  assert(
    HEAT_COLORS.length === 10,
    "Legend and badge scale must have ten levels",
  );
  let previousRedness = 0;
  for (let visits = 1; visits <= 10; visits++) {
    const current = visitBadgeStyle(visits).backgroundColor;
    const [red, green, blue] = current.slice(1).match(/../g)!.map((part) =>
      parseInt(part, 16)
    );
    assert(red > green && red > blue, `Visit ${visits} must use a red shade`);
    const redness = red - Math.max(green, blue);
    assert(
      redness > previousRedness,
      `Visit ${visits} must be redder than visit ${visits - 1}`,
    );
    previousRedness = redness;
  }
  assert(
    visitBadgeStyle(10).backgroundColor === "#ff0000",
    "A frequently visited badge should reach full red",
  );
});

Deno.test("heatmap: every badge shade has a readable count", () => {
  for (let visits = 0; visits <= 10; visits++) {
    const style = visitBadgeStyle(visits);
    const background = luminance(style.backgroundColor);
    const foreground = luminance(style.color);
    const contrast = (Math.max(background, foreground) + 0.05) /
      (Math.min(background, foreground) + 0.05);
    assert(contrast >= 4.5, `Visit ${visits} text contrast is ${contrast}`);
  }
});

Deno.test("heatmap: zero is neutral and badge heat saturates at ten", () => {
  const zero = visitBadgeStyle(0).backgroundColor;
  const [red, green, blue] = zero.slice(1).match(/../g)!.map((part) =>
    parseInt(part, 16)
  );
  assert(
    red <= green && red <= blue && zero !== visitBadgeStyle(1).backgroundColor,
    "Zero visits must have a neutral badge without red heat",
  );
  assert(
    JSON.stringify(visitBadgeStyle(10)) ===
      JSON.stringify(visitBadgeStyle(100)),
    "Heat should saturate at ten visits",
  );
});

Deno.test("heatmap: projected visits follow replay and ignore model calls or duplicate delivery", () => {
  const events = parseRecording(
    [
      { event: "run_started", stage: "runtime" },
      { event: "node_started", stage: "worker" },
      { event: "call_started", stage: "model", call: 1 },
      { event: "call_succeeded", stage: "model", call: 1 },
      { event: "node_finished", stage: "worker" },
      { event: "node_started", stage: "prover" },
      { event: "node_finished", stage: "prover" },
      { event: "node_started", stage: "worker" },
    ].map((event, index) =>
      JSON.stringify({
        run_id: "heat",
        timestamp: "2026-10-24T12:00:00Z",
        elapsed_seconds: index,
        ...event,
      })
    ).join("\n"),
  );
  const heatAt = (position: number, recording = events) =>
    visitBadgeStyle(
      projectAt(recording, position).visits.filter((visit) =>
        visit.nodeId === "worker"
      ).length,
    );
  assert(
    heatAt(0).backgroundColor === visitBadgeStyle(0).backgroundColor,
    "Replay restart must clear heat",
  );
  assert(
    heatAt(2).backgroundColor === heatAt(5).backgroundColor,
    "Model activity must not add visits",
  );
  assert(
    heatAt(8).backgroundColor !== heatAt(2).backgroundColor,
    "A second node visit must increase badge heat",
  );
  const duplicate = appendLiveEvent(events, events[7]);
  assert(
    heatAt(duplicate.length, duplicate).backgroundColor ===
      heatAt(8).backgroundColor,
    "SSE reconnect must not add heat",
  );
  assert(
    heatAt(0, []).backgroundColor === visitBadgeStyle(0).backgroundColor,
    "A new empty run must clear heat",
  );
});
