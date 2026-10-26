import { type EventEnvelope, parseEvent } from "../src/contracts.ts";

export type SourceScan = {
  events: EventEnvelope[];
  completeBytes: number;
  rejectedRecords: number;
  nearCapacity: boolean;
};

const encoder = new TextEncoder();
const MAX_BYTES = 1024 * 1024;
const MAX_RECORD_BYTES = 16 * 1024;

export async function readDiagnosticText(path: string): Promise<string> {
  if (Deno.build.os !== "windows") return await Deno.readTextFile(path);
  // DiagnosticSession locks byte zero while writing. Windows rejects reads
  // that overlap that byte, so read from byte one and restore JSON's '{'.
  const file = await Deno.open(path, { read: true });
  try {
    const size = (await file.stat()).size;
    if (size === 0) return "";
    if (size > MAX_BYTES) throw new Error("Diagnostic file exceeds 1 MiB");
    await file.seek(1, Deno.SeekMode.Start);
    const bytes = new Uint8Array(size);
    bytes[0] = 123;
    let offset = 1;
    while (offset < size) {
      const count = await file.read(bytes.subarray(offset));
      if (count === null) break;
      offset += count;
    }
    return new TextDecoder().decode(bytes.subarray(0, offset));
  } finally {
    file.close();
  }
}

export function scanSourceText(
  text: string,
  recordingId: string,
  runId: string,
): SourceScan {
  const bytes = encoder.encode(text);
  if (bytes.length > MAX_BYTES) {
    throw new Error("Diagnostic file exceeds 1 MiB");
  }
  const lines = text.split("\n");
  const events: EventEnvelope[] = [];
  let completeBytes = 0;
  let rejectedRecords = 0;
  let segment = 0;
  for (const raw of lines.slice(0, -1)) {
    const line = raw.endsWith("\r") ? raw.slice(0, -1) : raw;
    completeBytes += encoder.encode(raw + "\n").length;
    if (!line.trim() || encoder.encode(raw).length > MAX_RECORD_BYTES) {
      rejectedRecords++;
      continue;
    }
    try {
      const payload = parseEvent(JSON.parse(line));
      if (payload.run_id !== runId) {
        rejectedRecords++;
        continue;
      }
      if (payload.event === "run_started") segment++;
      events.push({
        schemaVersion: 1,
        recordingId,
        cursor: `${recordingId}:${completeBytes}`,
        ordinal: events.length + 1,
        segment,
        payload,
      });
    } catch {
      rejectedRecords++;
    }
  }
  return {
    events,
    completeBytes,
    rejectedRecords,
    nearCapacity: bytes.length >= MAX_BYTES - MAX_RECORD_BYTES,
  };
}

export function parseCursor(
  cursor: string | null,
  recordingId: string,
): number | null {
  if (!cursor) return 0;
  const prefix = `${recordingId}:`;
  if (!cursor.startsWith(prefix)) return null;
  const offset = cursor.slice(prefix.length);
  if (!/^(0|[1-9]\d{0,7})$/.test(offset)) return null;
  return Number(offset);
}
