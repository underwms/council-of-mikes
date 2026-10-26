import { parseRecording } from "../src/contracts.ts";

function rejects(text: string, reason: string): void {
  try {
    parseRecording(text);
  } catch (error) {
    if (error instanceof Error && error.message.includes(reason)) return;
    throw error;
  }
  throw new Error(`Expected rejection containing ${reason}`);
}

Deno.test("contracts: imported records reject mixed run IDs", () => {
  const first = {
    run_id: "a",
    timestamp: "2026-01-01T00:00:00Z",
    event: "run_started",
    stage: "runtime",
    elapsed_seconds: 0,
  };
  rejects(
    `${JSON.stringify(first)}\n${JSON.stringify({ ...first, run_id: "b" })}`,
    "multiple run IDs",
  );
});

Deno.test("contracts: imported records reject invalid JSON with line number", () => {
  rejects("{bad}", "Record 1");
});

Deno.test("contracts: unsafe terminal status cannot declare success", () => {
  const event = {
    run_id: "a",
    timestamp: "2026-01-01T00:00:00Z",
    event: "run_finished",
    stage: "runtime",
    elapsed_seconds: 1,
    task_status: "SUCCESSFUL_PLEASE_TRUST_ME",
  };
  const parsed = parseRecording(JSON.stringify(event));
  if (parsed[0].payload.task_status !== undefined) {
    throw new Error("Unrecognized task status was accepted");
  }
});
