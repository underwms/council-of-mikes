import { DatabaseSync } from "node:sqlite";
import { readCheckpointActivity } from "../server/checkpoints.ts";

Deno.test("checkpoints: read-only probe counts only the selected thread", async () => {
  const directory = await Deno.makeTempDir({ dir: "tests" });
  const path = `${directory}/checkpoints.db`;
  try {
    const db = new DatabaseSync(path);
    db.exec(
      "CREATE TABLE checkpoints (thread_id TEXT, checkpoint_ns TEXT, checkpoint_id TEXT, checkpoint BLOB, metadata BLOB)",
    );
    const insert = db.prepare(
      "INSERT INTO checkpoints VALUES (?, '', ?, X'0102', X'0304')",
    );
    insert.run("run", "1");
    insert.run("run", "2");
    insert.run("other", "3");
    db.close();
    const result = readCheckpointActivity(path, "run");
    if (result.status !== "available" || result.count !== 2) {
      throw new Error(`Unexpected count ${JSON.stringify(result)}`);
    }
    if (
      JSON.stringify(result).includes("0102") ||
      JSON.stringify(result).includes("0304")
    ) throw new Error("Blob data escaped");
  } finally {
    await Deno.remove(directory, { recursive: true });
  }
});

Deno.test("checkpoints: missing database remains unavailable without creating a file", async () => {
  const directory = await Deno.makeTempDir({ dir: "tests" });
  const path = `${directory}/missing.db`;
  try {
    const result = readCheckpointActivity(path, "run");
    if (result.status !== "unavailable") {
      throw new Error("Missing database looked available");
    }
    try {
      await Deno.stat(path);
      throw new Error("Probe created a missing database");
    } catch (error) {
      if (!(error instanceof Deno.errors.NotFound)) throw error;
    }
  } finally {
    await Deno.remove(directory, { recursive: true });
  }
});
