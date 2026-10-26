import { scanSourceText } from "../server/source.ts";
import { readDiagnosticText } from "../server/source.ts";

function equal(actual: unknown, expected: unknown, label: string): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(
      `${label}: ${JSON.stringify(actual)} != ${JSON.stringify(expected)}`,
    );
  }
}

const record = (event: string, elapsed_seconds = 0) =>
  JSON.stringify({
    run_id: "run",
    timestamp: "2026-01-01T00:00:00Z",
    event,
    stage: "runtime",
    elapsed_seconds,
  });

Deno.test("source: reader preserves the locked first byte and cursor offsets", async () => {
  const directory = await Deno.makeTempDir({ dir: "tests" });
  const path = `${directory}/run.jsonl`;
  const contents = `${record("run_started")}\n`;
  try {
    await Deno.writeTextFile(path, contents);
    equal(await readDiagnosticText(path), contents, "diagnostic text");
  } finally {
    await Deno.remove(directory, { recursive: true });
  }
});

Deno.test("source: trailing partial line is held until newline", () => {
  const text = `${record("run_started")}\n${
    record("run_finished").slice(0, -3)
  }`;
  const scan = scanSourceText(text, "generation", "run");
  equal(scan.events.length, 1, "events");
  equal(
    scan.completeBytes,
    new TextEncoder().encode(`${record("run_started")}\n`).length,
    "offset",
  );
});

Deno.test("source: invalid line does not hide a later valid record", () => {
  const scan = scanSourceText(
    `${record("run_started")}\n{invalid}\n${record("run_finished", 2)}\n`,
    "generation",
    "run",
  );
  equal(scan.events.map((event) => event.payload.event), [
    "run_started",
    "run_finished",
  ], "events");
  equal(scan.rejectedRecords, 1, "rejected count");
  equal(scan.events[1].ordinal, 2, "ordinal");
});

Deno.test("source: cursor uses byte offset and is stable on repeated scans", () => {
  const text = `${record("run_started")}\n`;
  const first = scanSourceText(text, "generation", "run");
  const second = scanSourceText(text, "generation", "run");
  equal(
    first.events[0].cursor,
    `generation:${new TextEncoder().encode(text).length}`,
    "cursor",
  );
  equal(second.events[0].cursor, first.events[0].cursor, "reconnect cursor");
});

Deno.test("source: record from another run is rejected", () => {
  const other = record("run_started").replace(
    '"run_id":"run"',
    '"run_id":"other"',
  );
  const scan = scanSourceText(
    `${other}\n${record("run_started")}\n`,
    "generation",
    "run",
  );
  equal(scan.events.length, 1, "events");
  equal(scan.rejectedRecords, 1, "rejected count");
});
