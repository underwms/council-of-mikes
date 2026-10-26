import { DatabaseSync } from "node:sqlite";

/** Read-only narration stream. Completion cursor is independent of source-event order. */
export function readNarrations(
  path: string,
  runId: string,
  after = 0,
  limit = 100,
): Record<string, unknown> {
  if (
    !/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(runId) ||
    !Number.isSafeInteger(after) || after < 0 ||
    !Number.isSafeInteger(limit) || limit < 1 || limit > 200
  ) throw new RangeError("Invalid narration query");
  let db: DatabaseSync | undefined;
  try {
    const info = Deno.lstatSync(path);
    if (!info.isFile || info.isSymlink || info.size > 128 * 1024 * 1024) {
      throw new Error("Unavailable storage");
    }
    db = new DatabaseSync(path, { readOnly: true, timeout: 100 });
    db.exec("PRAGMA query_only=ON");
    const version = db.prepare(
      "SELECT version FROM node_narration_meta LIMIT 2",
    ).all();
    if (version.length !== 1 || version[0].version !== 1) {
      return { version: 1, status: "unsupported_schema" };
    }
    const rows = db.prepare(
      "SELECT n.position,n.source_event_id,n.session_id,n.stage,n.visit_id,n.source_position,n.message,n.status,n.method,n.generated_at,n.accounting,s.generation AS session_generation,json_extract(v.payload,'$.timestamp') AS visit_started_at,json_extract(e.payload,'$.timestamp') AS source_timestamp " +
        "FROM node_narrations n JOIN observation_events e ON e.event_id=n.source_event_id AND e.run_id=n.run_id AND e.session_id=n.session_id AND e.position=n.source_position " +
        "JOIN observation_events v ON v.event_id=n.visit_id AND v.run_id=n.run_id AND v.session_id=n.session_id AND v.event='node_started' AND json_extract(v.payload,'$.stage')=n.stage " +
        "JOIN observation_sessions s ON s.run_id=n.run_id AND s.session_id=n.session_id WHERE n.run_id=? AND n.position>? ORDER BY n.position LIMIT ?",
    ).all(runId, after, limit);
    const items = rows.flatMap((row) => {
      if (
        typeof row.message !== "string" || !row.message.trim() ||
        row.message.length > 320 ||
        !["succeeded", "failed"].includes(String(row.status)) ||
        !["model", "event_derived"].includes(String(row.method))
      ) return [];
      const accounting = JSON.parse(String(row.accounting));
      const usage = Object.fromEntries(
        ["input_tokens", "output_tokens", "total_tokens", "cached_input_tokens"]
          .flatMap((key) => {
            const value = accounting?.usage?.[key];
            return typeof value === "number" && Number.isFinite(value) &&
                value >= 0
              ? [[key, value]]
              : [];
          }),
      );
      return [{
        position: row.position,
        source_event_id: row.source_event_id,
        session_id: row.session_id,
        session_generation: row.session_generation,
        stage: row.stage,
        visit_id: row.visit_id,
        source_position: row.source_position,
        source_timestamp: row.source_timestamp,
        visit_started_at: row.visit_started_at,
        message: row.message,
        status: row.status,
        method: row.method,
        generated_at: row.generated_at,
        accounting: {
          operation: "node_narration",
          usage,
          ...Object.fromEntries(
            [
              "provider",
              "requested_model",
              "returned_model",
              "cli_reported_model",
            ].flatMap((key) => {
              const value = accounting?.[key];
              return typeof value === "string" &&
                  /^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$/.test(value)
                ? [[key, value]]
                : [];
            }),
          ),
        },
      }];
    });
    return {
      version: 1,
      status: "available",
      items,
      next_cursor: rows.at(-1)?.position ?? after,
    };
  } catch {
    return { version: 1, status: "unavailable" };
  } finally {
    db?.close();
  }
}
