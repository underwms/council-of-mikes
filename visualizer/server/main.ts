import { join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  parseCursor,
  readDiagnosticText,
  scanSourceText,
  type SourceScan,
} from "./source.ts";
import { snapshotGraph } from "../src/topology.ts";
import { readCheckpointActivity } from "./checkpoints.ts";
import { readNarrations } from "./narrations.ts";
import { readObservations } from "./observations.ts";

export type ViewerOptions = {
  runId: string;
  diagnosticsDir: string;
  distDir: string;
  checkpointDb?: string;
  pollMs?: number;
};

const RUN_ID = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;
const encoder = new TextEncoder();

function json(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

async function loadSource(
  path: string,
  runId: string,
): Promise<SourceScan & { generation: string }> {
  const info = await Deno.lstat(path);
  if (!info.isFile || info.isSymlink) {
    throw new Error("Diagnostic source is not a regular file");
  }
  if (info.size > 1024 * 1024) {
    throw new Error("Diagnostic source exceeds 1 MiB");
  }
  const generation = `${runId}-${info.birthtime?.getTime() ?? 0}-${
    info.ino ?? 0
  }`;
  const scan = scanSourceText(
    await readDiagnosticText(path),
    generation,
    runId,
  );
  return { ...scan, generation };
}

function sourceStatus(error: unknown): string {
  if (error instanceof Deno.errors.NotFound) return "missing";
  if (error instanceof Error && error.message.includes("1 MiB")) {
    return "capped";
  }
  return "unavailable";
}

export function createHandler(
  options: ViewerOptions,
): (request: Request) => Promise<Response> {
  if (!RUN_ID.test(options.runId)) throw new Error("Invalid run ID");
  const path = join(options.diagnosticsDir, `${options.runId}.jsonl`);
  const pollMs = Math.max(20, options.pollMs ?? 250);
  let clients = 0;

  return async (request: Request): Promise<Response> => {
    const url = new URL(request.url);
    if (
      url.hostname !== "127.0.0.1" ||
      (request.headers.has("origin") &&
        request.headers.get("origin") !== url.origin)
    ) {
      return new Response("Forbidden", { status: 403 });
    }
    if (request.method !== "GET") {
      return new Response("Method not allowed", { status: 405 });
    }
    if (url.pathname.startsWith("/api/v1/runs/")) {
      const parts = url.pathname.split("/");
      if (parts.length !== 6 || parts[4] !== options.runId) {
        return json({ status: "not_found" }, 404);
      }
      try {
        const after = url.searchParams.get("after") ?? "0",
          limit = url.searchParams.get("limit") ?? "100";
        if (!/^\d{1,10}$/.test(after) || !/^\d{1,3}$/.test(limit)) {
          return json({ status: "invalid_query" }, 400);
        }
        if (parts[5] === "narrations") {
          return json(readNarrations(
            join(options.diagnosticsDir, "..", "observability.sqlite"),
            options.runId,
            Number(after),
            Number(limit),
          ));
        }
        return json(
          readObservations(
            join(options.diagnosticsDir, "..", "observability.sqlite"),
            options.runId,
            parts[5],
            Number(after),
            Number(limit),
            url.searchParams.get("group_by") ?? undefined,
          ),
        );
      } catch (error) {
        return json({
          status: error instanceof RangeError ? "invalid_query" : "unavailable",
        }, error instanceof RangeError ? 400 : 503);
      }
    }

    if (url.pathname === "/api/health") {
      try {
        await loadSource(path, options.runId);
        return json({ viewer: "ready", source: "available" });
      } catch (error) {
        return json({ viewer: "ready", source: sourceStatus(error) });
      }
    }
    if (url.pathname === "/api/graph") return json(snapshotGraph);
    if (url.pathname === "/api/checkpoint") {
      return json(
        options.checkpointDb
          ? readCheckpointActivity(options.checkpointDb, options.runId)
          : { status: "unavailable" },
      );
    }
    if (url.pathname === "/api/runs") return json([{ runId: options.runId }]);

    if (url.pathname === `/api/runs/${options.runId}/events`) {
      if (clients >= 4) {
        return new Response("Too many streams", { status: 429 });
      }
      const after = url.searchParams.get("after");
      const lastEventId = request.headers.get("last-event-id");
      if (after && lastEventId && after !== lastEventId) {
        return new Response("Conflicting cursors", { status: 400 });
      }
      const requestedCursor = after ?? lastEventId;
      if (
        requestedCursor && !/^[A-Za-z0-9_-]+:\d{1,8}$/.test(requestedCursor)
      ) {
        return new Response("Invalid cursor", { status: 400 });
      }
      clients++;
      let timer: ReturnType<typeof setInterval> | undefined;
      let heartbeat: ReturnType<typeof setInterval> | undefined;
      let closed = false;
      let polling = false;
      let generation: string | undefined;
      let offset = 0;
      let lastStatus = "";
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          const close = () => {
            if (closed) return;
            closed = true;
            if (timer !== undefined) clearInterval(timer);
            if (heartbeat !== undefined) clearInterval(heartbeat);
            clients--;
            try {
              controller.close();
            } catch { /* already closed */ }
          };
          const send = (name: string, value: unknown, id?: string) => {
            if (closed) return;
            const wire = `${id ? `id: ${id}\n` : ""}event: ${name}\ndata: ${
              JSON.stringify(value)
            }\n\n`;
            const bytes = encoder.encode(wire);
            if ((controller.desiredSize ?? 0) < bytes.length) {
              close();
              return;
            }
            controller.enqueue(bytes);
          };
          const tick = async () => {
            if (closed || polling) return;
            polling = true;
            try {
              const scan = await loadSource(path, options.runId);
              if (
                generation !== scan.generation || scan.completeBytes < offset
              ) {
                if (generation !== undefined) {
                  send("reset", { reason: "recording_changed" });
                }
                generation = scan.generation;
                const requestedOffset = parseCursor(
                  requestedCursor,
                  generation,
                );
                if (requestedCursor && requestedOffset === null) {
                  send("reset", { reason: "stale_cursor" });
                }
                offset = requestedOffset ?? 0;
                if (offset > scan.completeBytes) {
                  send("reset", { reason: "stale_cursor" });
                  offset = 0;
                }
              }
              for (const event of scan.events) {
                const recordOffset = Number(
                  event.cursor.slice(event.cursor.lastIndexOf(":") + 1),
                );
                if (recordOffset > offset) {
                  send("record", event, event.cursor);
                  offset = recordOffset;
                }
              }
              const status = scan.nearCapacity ? "near_capacity" : "available";
              if (status !== lastStatus || scan.rejectedRecords > 0) {
                send("source_status", {
                  status,
                  rejectedRecords: scan.rejectedRecords,
                });
                lastStatus = status;
              }
            } catch (error) {
              const status = sourceStatus(error);
              if (status !== lastStatus) {
                send("source_status", { status });
                lastStatus = status;
              }
            } finally {
              polling = false;
            }
          };
          void tick();
          timer = setInterval(() => void tick(), pollMs);
          heartbeat = setInterval(() => {
            if (closed) return;
            const bytes = encoder.encode(": heartbeat\n\n");
            if ((controller.desiredSize ?? 0) < bytes.length) close();
            else controller.enqueue(bytes);
          }, 15_000);
        },
        cancel() {
          if (timer !== undefined) clearInterval(timer);
          if (heartbeat !== undefined) clearInterval(heartbeat);
          if (!closed) clients--;
          closed = true;
        },
      }, { highWaterMark: 256 * 1024, size: (chunk) => chunk.byteLength });
      return new Response(stream, {
        headers: {
          "content-type": "text/event-stream",
          "cache-control": "no-store",
          "x-accel-buffering": "no",
        },
      });
    }

    const relative = url.pathname === "/"
      ? "index.html"
      : url.pathname === "/sample-events.jsonl"
      ? "sample-events.jsonl"
      : /^\/assets\/[A-Za-z0-9._-]+\.(js|css)$/.test(url.pathname)
      ? url.pathname.slice(1)
      : null;
    if (!relative) return new Response("Not found", { status: 404 });
    try {
      const bytes = await Deno.readFile(join(options.distDir, relative));
      const mime = relative.endsWith(".js")
        ? "text/javascript"
        : relative.endsWith(".css")
        ? "text/css"
        : relative.endsWith(".jsonl")
        ? "application/x-ndjson"
        : "text/html";
      return new Response(bytes, {
        headers: {
          "content-type": `${mime}; charset=utf-8`,
          "cache-control": "no-store",
        },
      });
    } catch {
      return new Response("Not found", { status: 404 });
    }
  };
}

if (import.meta.main) {
  const args = Deno.args;
  const option = (name: string) => args[args.indexOf(name) + 1];
  if (!args.includes("--run-id") || !args.includes("--diagnostics-dir")) {
    throw new Error("Usage: --run-id ID --diagnostics-dir PATH [--port PORT]");
  }
  const runId = option("--run-id");
  const diagnosticsDir = option("--diagnostics-dir");
  const checkpointDb = args.includes("--checkpoint-db")
    ? option("--checkpoint-db")
    : undefined;
  const port = args.includes("--port") ? Number(option("--port")) : 0;
  if (!Number.isSafeInteger(port) || port < 0 || port > 65535) {
    throw new Error("Invalid port");
  }
  const distDir = fileURLToPath(new URL("../dist/", import.meta.url));
  const shutdown = new AbortController();
  Deno.serve({
    hostname: "127.0.0.1",
    port,
    signal: shutdown.signal,
    onListen: ({ port }) => {
      console.log(`http://127.0.0.1:${port}/?run=${encodeURIComponent(runId)}`);
    },
  }, createHandler({ runId, diagnosticsDir, distDir, checkpointDb }));
  if (args.includes("--watch-stdin")) {
    // The Python CLI holds the pipe open. Keep the run available briefly after
    // its process exits so the final timeline can still be inspected.
    try {
      await Deno.stdin.read(new Uint8Array(1));
    } catch {
      // A closed pipe has the same lifecycle meaning as EOF.
    }
    setTimeout(() => shutdown.abort(), 10 * 60_000);
  }
}
