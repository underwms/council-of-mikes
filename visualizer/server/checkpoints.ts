import { DatabaseSync } from "node:sqlite";

export type CheckpointActivity =
  | { status: "available"; count: number }
  | { status: "unavailable" };

export function readCheckpointActivity(
  path: string,
  runId: string,
): CheckpointActivity {
  let db: DatabaseSync | undefined;
  try {
    db = new DatabaseSync(path, { readOnly: true, timeout: 100 });
    db.exec("PRAGMA query_only=ON");
    const result = db.prepare(
      "SELECT COUNT(*) AS count FROM checkpoints WHERE thread_id = ? AND checkpoint_ns = ''",
    ).get(runId) as { count?: unknown } | undefined;
    if (
      typeof result?.count !== "number" || !Number.isSafeInteger(result.count)
    ) {
      return { status: "unavailable" };
    }
    return { status: "available", count: result.count };
  } catch {
    return { status: "unavailable" };
  } finally {
    db?.close();
  }
}
