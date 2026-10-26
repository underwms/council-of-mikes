import { createHandler } from "../server/main.ts";
import { DatabaseSync } from "node:sqlite";

function assert(condition: boolean, message: string): void {
  if (!condition) throw new Error(message);
}

const base = "http://127.0.0.1:8123";

Deno.test("streams: health stays local and reveals no checkpoint payload", async () => {
  const handler = createHandler({
    runId: "run",
    diagnosticsDir: "tests/fixtures",
    distDir: "dist",
  });
  const response = await handler(new Request(`${base}/api/health`));
  assert(response.status === 200, `Unexpected status ${response.status}`);
  const body = await response.text();
  assert(body.includes("viewer"), "Health body missing viewer status");
  assert(
    !body.includes("checkpoint") && !body.includes("task_input"),
    "Health body exposes state",
  );
  const rejected = await handler(
    new Request(`${base}/api/health`, {
      headers: { Origin: "https://elsewhere.example" },
    }),
  );
  assert(rejected.status === 403, "Cross-origin request was accepted");
});

Deno.test("streams: SSE sends the complete backlog with stable IDs", async () => {
  const directory = await Deno.makeTempDir({ dir: "tests" });
  try {
    const record = (event: string) =>
      JSON.stringify({
        run_id: "run",
        timestamp: "2026-01-01T00:00:00Z",
        event,
        stage: "runtime",
        elapsed_seconds: 0,
      });
    await Deno.writeTextFile(
      `${directory}/run.jsonl`,
      `${record("run_started")}\n${record("run_finished")}\n`,
    );
    const handler = createHandler({
      runId: "run",
      diagnosticsDir: directory,
      distDir: "dist",
      pollMs: 20,
    });
    const abort = new AbortController();
    const response = await handler(
      new Request(`${base}/api/runs/run/events`, { signal: abort.signal }),
    );
    assert(response.status === 200, `Unexpected status ${response.status}`);
    assert(
      response.headers.get("content-type") === "text/event-stream",
      "Wrong content type",
    );
    const reader = response.body!.getReader();
    const chunk = new TextDecoder().decode((await reader.read()).value);
    assert(
      chunk.includes("event: record") && chunk.includes("run_started"),
      "First record missing",
    );
    assert(chunk.includes("id: "), "Cursor missing");
    abort.abort();
    await reader.cancel();
  } finally {
    await Deno.remove(directory, { recursive: true });
  }
});

Deno.test("streams: an appended record arrives on the open stream", async () => {
  const directory = await Deno.makeTempDir({ dir: "tests" });
  const path = `${directory}/run.jsonl`;
  const record = (event: string) =>
    JSON.stringify({
      run_id: "run",
      timestamp: "2026-01-01T00:00:00Z",
      event,
      stage: event === "node_started" ? "architect" : "runtime",
      elapsed_seconds: 0,
    });
  try {
    await Deno.writeTextFile(path, `${record("run_started")}\n`);
    const handler = createHandler({
      runId: "run",
      diagnosticsDir: directory,
      distDir: "dist",
      pollMs: 20,
    });
    const response = await handler(new Request(`${base}/api/runs/run/events`));
    const reader = response.body!.getReader();
    await reader.read();
    await Deno.writeTextFile(path, `${record("node_started")}\n`, {
      append: true,
    });
    const deadline = Date.now() + 1000;
    let text = "";
    while (!text.includes("node_started") && Date.now() < deadline) {
      const next = await Promise.race([
        reader.read(),
        new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error("SSE append timed out")), 1000)
        ),
      ]);
      text += new TextDecoder().decode(next.value);
    }
    assert(
      text.includes("node_started"),
      "Appended stage event did not arrive",
    );
    await reader.cancel();
  } finally {
    await Deno.remove(directory, { recursive: true });
  }
});

Deno.test("streams: reconnect cursor resumes after the acknowledged record", async () => {
  const directory = await Deno.makeTempDir({ dir: "tests" });
  try {
    const record = (event: string) =>
      JSON.stringify({
        run_id: "run",
        timestamp: "2026-01-01T00:00:00Z",
        event,
        stage: "runtime",
        elapsed_seconds: 0,
      });
    const first = `${record("run_started")}\n`;
    await Deno.writeTextFile(
      `${directory}/run.jsonl`,
      `${first}${record("run_finished")}\n`,
    );
    const handler = createHandler({
      runId: "run",
      diagnosticsDir: directory,
      distDir: "dist",
      pollMs: 20,
    });
    const health = await handler(new Request(`${base}/api/health`));
    assert(health.status === 200, "Health failed");
    const initial = await handler(new Request(`${base}/api/runs/run/events`));
    const initialReader = initial.body!.getReader();
    const firstChunk = new TextDecoder().decode(
      (await initialReader.read()).value,
    );
    const match = firstChunk.match(/^id: ([^\n]+)/m);
    assert(Boolean(match), "Initial cursor missing");
    await initialReader.cancel();
    const resumed = await handler(
      new Request(
        `${base}/api/runs/run/events?after=${encodeURIComponent(match![1])}`,
      ),
    );
    const reader = resumed.body!.getReader();
    const chunk = new TextDecoder().decode((await reader.read()).value);
    assert(chunk.includes("run_finished"), "Next event missing");
    assert(!chunk.includes("run_started"), "Acknowledged event was replayed");
    await reader.cancel();
  } finally {
    await Deno.remove(directory, { recursive: true });
  }
});

Deno.test("streams: stale recording cursor explicitly resets before replay", async () => {
  const directory = await Deno.makeTempDir({ dir: "tests" });
  try {
    await Deno.writeTextFile(
      `${directory}/run.jsonl`,
      `${
        JSON.stringify({
          run_id: "run",
          timestamp: "2026-01-01T00:00:00Z",
          event: "run_started",
          stage: "runtime",
          elapsed_seconds: 0,
        })
      }\n`,
    );
    const handler = createHandler({
      runId: "run",
      diagnosticsDir: directory,
      distDir: "dist",
      pollMs: 20,
    });
    const response = await handler(
      new Request(`${base}/api/runs/run/events?after=stale:10`),
    );
    const reader = response.body!.getReader();
    const first = new TextDecoder().decode((await reader.read()).value);
    assert(first.includes("event: reset"), "Stale cursor reset was omitted");
    await reader.cancel();
  } finally {
    await Deno.remove(directory, { recursive: true });
  }
});

Deno.test("streams: checkpoint route exposes only count metadata", async () => {
  const directory = await Deno.makeTempDir({ dir: "tests" });
  const path = `${directory}/checkpoints.db`;
  try {
    const db = new DatabaseSync(path);
    db.exec(
      "CREATE TABLE checkpoints (thread_id TEXT, checkpoint_ns TEXT, checkpoint BLOB)",
    );
    db.prepare("INSERT INTO checkpoints VALUES ('run', '', X'0102')").run();
    db.close();
    const handler = createHandler({
      runId: "run",
      diagnosticsDir: directory,
      distDir: "dist",
      checkpointDb: path,
    });
    const response = await handler(new Request(`${base}/api/checkpoint`));
    const text = await response.text();
    assert(
      response.status === 200 && text.includes('"count":1'),
      "Checkpoint count missing",
    );
    assert(
      !text.includes("0102") && !text.includes("checkpoint_id"),
      "Checkpoint payload leaked",
    );
  } finally {
    await Deno.remove(directory, { recursive: true });
  }
});
