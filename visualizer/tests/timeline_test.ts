import { positionAtElapsed } from "../src/timeline.ts";
import { parseRecording } from "../src/contracts.ts";

function equal(actual: unknown, expected: unknown): void {
  if (actual !== expected) {
    throw new Error(`Expected ${expected}, got ${actual}`);
  }
}

Deno.test("timeline: applies every event due at the same elapsed time", () => {
  const base = {
    run_id: "run",
    timestamp: "2026-01-01T00:00:00Z",
    stage: "worker",
  };
  const records = [0, 1, 1, 2].map((elapsed_seconds) =>
    JSON.stringify({ ...base, event: "node_started", elapsed_seconds })
  ).join("\n");
  equal(positionAtElapsed(parseRecording(records), 1), 3);
});

Deno.test("timeline: end of real excerpt applies 37 records", async () => {
  const text = await Deno.readTextFile("tests/fixtures/sample-events.jsonl");
  const events = parseRecording(text);
  equal(positionAtElapsed(events, 262.022), 37);
  equal(positionAtElapsed(events, 0), 0);
});
